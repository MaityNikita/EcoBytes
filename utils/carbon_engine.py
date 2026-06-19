"""
Carbon Engine — converts raw digital usage into CO₂e estimates.

Emission factors sourced from:
  - IEA Electricity Emissions Factors 2023 (global avg: 0.233 kg CO₂e/kWh)
  - Shift Project "Climate Crisis: Unsustainable Usage of Online Video" (2019)
  - Lannelongue et al., Green Algorithms (2021)
  - BCG Digital Carbon Footprint study (2022)
"""

from dataclasses import dataclass, field
from typing import Dict, List

# ── Emission Factors (gCO₂e per unit) ────────────────────────────────────────

EF = {
    # Email
    'email_sent_g':       4.0,    # g CO₂e per email sent (with avg attachment)
    'email_received_g':   0.3,    # g CO₂e per email received/stored
    'email_spam_g':       0.03,   # g CO₂e per spam (smaller, quickly deleted)

    # Storage (cloud)
    'storage_gb_year_g':  3.0,    # g CO₂e per GB/year stored in cloud

    # Devices (operational energy)
    'laptop_hour_g':      36.0,   # g CO₂e per hour of laptop use
    'phone_hour_g':       8.0,    # g CO₂e per hour of phone use
    'desktop_hour_g':     55.0,   # g CO₂e per hour of desktop use
    'tablet_hour_g':      12.0,

    # Video streaming
    'video_sd_hour_g':    36.0,   # g CO₂e per hour (SD)
    'video_hd_hour_g':    55.0,   # g CO₂e per hour (HD)
    'video_4k_hour_g':    97.0,   # g CO₂e per hour (4K)

    # Audio streaming
    'audio_hour_g':       0.8,    # g CO₂e per hour

    # Data transfer / sync
    'data_gb_g':          7.0,    # g CO₂e per GB transferred

    # Web activity
    'search_query_g':     0.2,    # g CO₂e per search query
    'ai_query_g':         4.3,    # g CO₂e per LLM query (avg inference)
}

STREAMING_FACTORS = {
    'SD': EF['video_sd_hour_g'],
    'HD': EF['video_hd_hour_g'],
    '4K': EF['video_4k_hour_g'],
}


class CarbonEngine:

    def calculate(self, raw: dict) -> dict:
        """Return breakdown dict with per-category and per-device gCO₂e/month."""
        result = {}

        # Gmail
        gmail = raw.get('gmail', {})
        result['email'] = {
            'sent': round(gmail.get('emails_sent_30d', 0) * EF['email_sent_g']),
            'received': round(gmail.get('emails_received_30d', 0) * EF['email_received_g']),
            'spam': round(gmail.get('spam_count', 0) * EF['email_spam_g']),
            'storage': round(gmail.get('storage_gb', 0) * EF['storage_gb_year_g'] / 12),
        }
        result['email']['total'] = sum(result['email'].values())

        # Drive
        drive = raw.get('drive', {})
        result['storage'] = {
            'drive_total': round(drive.get('total_storage_gb', 0) * EF['storage_gb_year_g'] / 12),
            'large_files': round(drive.get('large_files_gb', 0) * EF['storage_gb_year_g'] / 12),
        }
        result['storage']['total'] = result['storage']['drive_total']

        # Devices
        devices_raw = raw.get('devices', [])
        result['devices'] = []
        total_device_g = 0
        for d in devices_raw:
            dtype = d.get('type', 'laptop')
            ef_key = f"{dtype}_hour_g" if f"{dtype}_hour_g" in EF else 'laptop_hour_g'
            screen_g = round(d.get('screen_hours_day', 0) * 30 * EF[ef_key])
            video_g = round(d.get('video_hours_day', 0) * 30 * EF['video_hd_hour_g'])
            sync_g = round(d.get('cloud_sync_gb_month', 0) * EF['data_gb_g'])
            device_total = screen_g + video_g + sync_g
            total_device_g += device_total
            result['devices'].append({
                'name': d.get('name', dtype.capitalize()),
                'type': dtype,
                'screen_g': screen_g,
                'video_g': video_g,
                'sync_g': sync_g,
                'total': device_total
            })
        result['devices_total'] = total_device_g

        # Streaming
        streaming = raw.get('streaming', {})
        quality = streaming.get('video_quality', 'HD')
        vef = STREAMING_FACTORS.get(quality, EF['video_hd_hour_g'])
        result['streaming'] = {
            'video': round(streaming.get('video_hours_month', 0) * vef),
            'audio': round(streaming.get('audio_hours_month', 0) * EF['audio_hour_g']),
        }
        result['streaming']['total'] = sum(result['streaming'].values())

        # Web activity
        search = raw.get('search', {})
        result['web'] = {
            'searches': round(search.get('searches_day', 0) * 30 * EF['search_query_g']),
            'ai_queries': round(search.get('ai_queries_month', 0) * EF['ai_query_g']),
        }
        result['web']['total'] = sum(result['web'].values())

        # Grand total (gCO₂e/month) + convert to kgCO₂e
        total_g = (
            result['email']['total'] +
            result['storage']['total'] +
            total_device_g +
            result['streaming']['total'] +
            result['web']['total']
        )
        result['grand_total_g'] = total_g
        result['grand_total_kg'] = round(total_g / 1000, 3)
        result['grand_total_kg_year'] = round(total_g / 1000 * 12, 2)

        return result

    def eco_score(self, footprint: dict) -> dict:
        """Return A–E letter score and 0–100 numeric score."""
        kg_month = footprint.get('grand_total_kg', 0)
        # Benchmarks: avg digital footprint ~50 kg CO₂e/month
        # Sources: Shift Project, BCG Digital Carbon study
        thresholds = [
            (15,  'A', 'Excellent', '#1D9E75'),
            (25,  'B', 'Good',      '#5DCAA5'),
            (40,  'C', 'Moderate',  '#BA7517'),
            (60,  'D', 'High',      '#D85A30'),
            (999, 'E', 'Very high', '#A32D2D'),
        ]
        for limit, grade, label, color in thresholds:
            if kg_month <= limit:
                score = max(0, round(100 - (kg_month / 60 * 100)))
                return {'grade': grade, 'label': label, 'color': color, 'score': score, 'kg_month': round(kg_month, 1)}
        return {'grade': 'E', 'label': 'Very high', 'color': '#A32D2D', 'score': 0, 'kg_month': round(kg_month, 1)}

    def recommendations(self, footprint: dict) -> List[dict]:
        """Return ranked, actionable recommendations based on the footprint breakdown."""
        recs = []

        email = footprint.get('email', {})
        storage = footprint.get('storage', {})
        streaming = footprint.get('streaming', {})
        web = footprint.get('web', {})
        devices = footprint.get('devices', [])

        if email.get('spam', 0) > 100:
            recs.append({
                'category': 'Email',
                'icon': 'envelope',
                'priority': 'quick win',
                'title': 'Unsubscribe from unused newsletters',
                'detail': f"You receive ~{email.get('spam',0)//30} spam/promotional emails per day. Unsubscribing saves server processing and storage energy.",
                'saving_g_month': email.get('spam', 0),
                'effort': 'low'
            })

        if storage.get('large_files_gb', 0) > 5:
            recs.append({
                'category': 'Storage',
                'icon': 'cloud',
                'priority': 'medium impact',
                'title': 'Delete or compress large unused files',
                'detail': f"Large files in Drive account for significant idle cloud energy. Aim to halve storage with periodic cleanup.",
                'saving_g_month': round(storage.get('drive_total', 0) * 0.4),
                'effort': 'medium'
            })

        video_g = streaming.get('video', 0)
        if video_g > 2000:
            recs.append({
                'category': 'Streaming',
                'icon': 'play-circle',
                'priority': 'high impact',
                'title': 'Lower video streaming quality on small screens',
                'detail': "Switching from HD to SD on your phone saves ~34% of streaming emissions with barely perceptible quality loss.",
                'saving_g_month': round(video_g * 0.34),
                'effort': 'low'
            })

        ai_g = web.get('ai_queries', 0)
        if ai_g > 200:
            recs.append({
                'category': 'AI usage',
                'icon': 'cpu',
                'priority': 'medium impact',
                'title': 'Batch AI queries instead of many small ones',
                'detail': "LLM inference is energy-intensive. Combining related questions into one prompt reduces total compute used.",
                'saving_g_month': round(ai_g * 0.3),
                'effort': 'low'
            })

        for d in devices:
            if d.get('screen_g', 0) > 3000:
                recs.append({
                    'category': f"Device — {d['name']}",
                    'icon': 'monitor',
                    'priority': 'high impact',
                    'title': f"Reduce idle screen time on {d['name']}",
                    'detail': "Enabling aggressive sleep/auto-lock reduces device draw significantly. Every idle hour costs energy.",
                    'saving_g_month': round(d['screen_g'] * 0.15),
                    'effort': 'low'
                })

        recs.append({
            'category': 'General',
            'icon': 'sun',
            'priority': 'long term',
            'title': 'Schedule heavy tasks for off-peak grid hours',
            'detail': "Grids are greener at night in many regions. Running backups, syncs, and large uploads between 11pm–6am can halve their carbon cost.",
            'saving_g_month': round(footprint.get('grand_total_g', 0) * 0.08),
            'effort': 'medium'
        })

        # Sort by saving
        recs.sort(key=lambda r: r['saving_g_month'], reverse=True)
        return recs

    def get_peer_benchmark(self, country: str, industry: str) -> dict:
        """Return peer comparison average in kg CO2e/month."""
        # Base global average ~50 kg/mo
        base = 50.0
        
        # Country adjustments
        if country == 'US':
            base *= 1.4 # Higher device ownership and streaming
        elif country == 'IN':
            base *= 0.6 # Lower average digital consumption per capita
        elif country == 'UK':
            base *= 1.1
            
        # Industry adjustments
        if industry == 'Tech':
            base *= 1.5 # High screen time, heavy cloud usage
        elif industry == 'Finance':
            base *= 1.3
        elif industry == 'Education':
            base *= 1.1
            
        return {
            'avg_kg_month': round(base, 1),
            'label': f"{industry if industry != 'Other' else 'Average'} worker in {country if country != 'Global' else 'the World'}"
        }
