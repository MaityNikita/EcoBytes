from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    refresh_token = db.Column(db.String(255), nullable=True)
    # Storing serialized devices as JSON string
    devices = db.Column(db.Text, nullable=True)
    # Storing youtube estimates
    youtube_hours = db.Column(db.Float, nullable=True)
    energy_region = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    
    # Relationships
    goal = db.relationship('Goal', backref='user', uselist=False)
    footprints = db.relationship('FootprintLog', backref='user', lazy=True)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('user.id'), nullable=False)
    target_reduction_pct = db.Column(db.Float, nullable=False) # e.g. 20 for 20%
    target_kg_month = db.Column(db.Float, nullable=False) # calculated baseline target
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class FootprintLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('user.id'), nullable=False)
    date_logged = db.Column(db.DateTime, server_default=db.func.now())
    total_kg = db.Column(db.Float, nullable=False)
    raw_data = db.Column(db.Text, nullable=False) # JSON
