import os
import json
from flask import Flask, redirect, url_for, session, render_template, jsonify, request
from authlib.integrations.flask_client import OAuth
from datetime import datetime, timedelta
from utils.carbon_engine import CarbonEngine
from utils.google_data import GoogleDataCollector
from dotenv import load_dotenv

load_dotenv()

from models import db, User, Goal, FootprintLog

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
app.config['SESSION_COOKIE_SECURE'] = os.environ.get("FLASK_ENV") == "production"

# Database Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///ecobytes.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/drive.metadata.readonly https://www.googleapis.com/auth/youtube.readonly',
        'prompt': 'consent', # to ensure we get refresh token
        'access_type': 'offline'
    }
)

# ── CLI Commands ──────────────────────────────────────────────────────────────

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database initialized.")

@app.cli.command("send-digests")
def send_digests():
    from utils.mailer import send_weekly_digest
    users = User.query.all()
    for user in users:
        # In a real scenario, use refresh token to get new access token
        # For simplicity, we just send digest with last known data if available
        # or mock the background job
        if user.footprints:
            last_fp = user.footprints[-1]
            send_weekly_digest(user, last_fp)
    print("Digests sent.")

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html', user=user)

@app.route('/login')
def login():
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri, access_type='offline', prompt='consent')

@app.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    sub = user_info['sub']
    user = User.query.get(sub)
    if not user:
        user = User(
            id=sub, 
            email=user_info['email'], 
            name=user_info['name']
        )
        db.session.add(user)
        
    # Update refresh token if provided
    if 'refresh_token' in token:
        user.refresh_token = token['refresh_token']
        
    db.session.commit()
    
    session['user'] = {
        'email': user.email,
        'name': user.name,
        'picture': user_info.get('picture', ''),
        'sub': user.id
    }
    session['token'] = token

    if not user.devices:
        return redirect(url_for('onboarding'))
        
    return redirect(url_for('dashboard'))

@app.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    if 'user' not in session:
        return redirect(url_for('index'))
        
    user = User.query.get(session['user']['sub'])
    
    if request.method == 'POST':
        devices_data = request.form.getlist('devices')
        hours = request.form.get('hours', 4)
        youtube_hours = request.form.get('youtube_hours', 1)
        region = request.form.get('region', 'Global')
        country = request.form.get('country', 'Global')
        industry = request.form.get('industry', 'Other')
        
        devices = []
        for d in devices_data:
            devices.append({
                'name': d.capitalize(),
                'type': d,
                'screen_hours_day': float(hours),
                'video_hours_day': float(youtube_hours),
                'cloud_sync_gb_month': 2.0
            })
            
        user.devices = json.dumps(devices)
        user.youtube_hours = float(youtube_hours)
        user.energy_region = region
        user.country = country
        user.industry = industry
        db.session.commit()
        return redirect(url_for('dashboard'))
        
    return render_template('onboarding.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', user=session['user'])

@app.route('/api/goals', methods=['POST'])
def set_goal():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user = User.query.get(session['user']['sub'])
    data = request.json
    pct = data.get('target_pct', 10)
    baseline = data.get('baseline_kg', 50)
    
    if user.goal:
        user.goal.target_reduction_pct = pct
        user.goal.target_kg_month = baseline * (1 - (pct/100))
    else:
        goal = Goal(user_id=user.id, target_reduction_pct=pct, target_kg_month=baseline * (1 - (pct/100)))
        db.session.add(goal)
        
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/footprint')
def api_footprint():
    """Main API: collect data + calculate carbon footprint."""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    token = session.get('token', {})
    access_token = token.get('access_token')
    
    user = User.query.get(session['user']['sub'])

    collector = GoogleDataCollector(access_token)
    engine = CarbonEngine()

    raw = collector.collect_all()
    
    # Inject user's device overrides and youtube estimates if set
    if user.devices:
        raw['devices'] = json.loads(user.devices)
    if user.youtube_hours is not None:
        raw['streaming']['video_hours_month'] = user.youtube_hours * 30
        
    # Attempt to fetch YouTube watch stats
    yt_stats = collector.collect_youtube_stats()
    if yt_stats:
        # If we successfully get liked videos/subscriptions to estimate higher usage, override
        if yt_stats.get('estimated_hours_month') > raw['streaming']['video_hours_month']:
            raw['streaming']['video_hours_month'] = yt_stats['estimated_hours_month']

    footprint = engine.calculate(raw)
    
    # Save log to DB
    log = FootprintLog(user_id=user.id, total_kg=footprint['grand_total_kg'], raw_data=json.dumps(raw))
    db.session.add(log)
    db.session.commit()
    
    # Goal info
    goal_info = None
    if user.goal:
        goal_info = {
            'target_pct': user.goal.target_reduction_pct,
            'target_kg': round(user.goal.target_kg_month, 1),
            'progress_pct': max(0, min(100, (1 - (footprint['grand_total_kg'] / (user.goal.target_kg_month / (1 - user.goal.target_reduction_pct/100)))) * 100)) if user.goal.target_kg_month > 0 else 0
        }
        
    # Historical Data
    logs = FootprintLog.query.filter_by(user_id=user.id).order_by(FootprintLog.date_logged.asc()).all()
    history = [{'date': l.date_logged.strftime('%Y-%m-%d'), 'kg': l.total_kg} for l in logs]
    
    # Peer Benchmark
    peer_data = engine.get_peer_benchmark(user.country or 'Global', user.industry or 'Other')

    return jsonify({
        'user': session['user'],
        'generated_at': datetime.utcnow().isoformat(),
        'raw_usage': raw,
        'footprint': footprint,
        'recommendations': engine.recommendations(footprint),
        'score': engine.eco_score(footprint),
        'goal': goal_info,
        'history': history,
        'peers': peer_data
    })

@app.route('/api/demo')
def api_demo():
    """Demo mode — no login needed, uses synthetic data."""
    engine = CarbonEngine()
    raw = _demo_data()
    footprint = engine.calculate(raw)
    return jsonify({
        'user': {'name': 'Demo User', 'email': 'demo@example.com', 'picture': ''},
        'generated_at': datetime.utcnow().isoformat(),
        'raw_usage': raw,
        'footprint': footprint,
        'recommendations': engine.recommendations(footprint),
        'score': engine.eco_score(footprint),
        'goal': {'target_pct': 20, 'target_kg': 40.0, 'progress_pct': 45}
    })

def _demo_data():
    return {
        'gmail': {'emails_sent_30d': 320, 'emails_received_30d': 1850, 'storage_gb': 12.4, 'spam_count': 430},
        'drive': {'total_storage_gb': 28.7, 'files_count': 1240, 'shared_files': 87, 'large_files_gb': 14.2},
        'devices': [
            {'name': 'Laptop', 'type': 'laptop', 'screen_hours_day': 8, 'video_hours_day': 2.5, 'cloud_sync_gb_month': 4.2},
            {'name': 'Phone', 'type': 'phone', 'screen_hours_day': 4.5, 'video_hours_day': 1.5, 'cloud_sync_gb_month': 1.8}
        ],
        'streaming': {'video_hours_month': 120, 'audio_hours_month': 60, 'video_quality': 'HD'},
        'search': {'searches_day': 35, 'ai_queries_month': 80}
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # In a real app we'd init db inside app context or via CLI, doing it here for ease
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') != 'production')
