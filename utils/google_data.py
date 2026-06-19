"""
GoogleDataCollector — fetches real usage data from Google APIs.
Falls back to estimates when scopes are limited.
"""

import requests
from datetime import datetime, timedelta


class GoogleDataCollector:
    BASE = "https://www.googleapis.com"

    def __init__(self, access_token: str):
        self.token = access_token
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def collect_all(self) -> dict:
        return {
            'gmail': self._gmail_stats(),
            'drive': self._drive_stats(),
            'devices': self._device_estimates(),
            'streaming': self._streaming_estimate(),
            'search': self._search_estimate(),
        }

    def collect_youtube_stats(self) -> dict:
        try:
            # We use subscriptions or liked videos to estimate activity if watch history isn't directly available via v3 API.
            # This is a proxy measurement.
            res = requests.get(
                f"{self.BASE}/youtube/v3/channels?part=statistics&mine=true",
                headers=self.headers, timeout=8
            ).json()
            
            if 'items' in res and len(res['items']) > 0:
                stats = res['items'][0].get('statistics', {})
                view_count = int(stats.get('viewCount', 0))
                video_count = int(stats.get('videoCount', 0))
                subscriber_count = int(stats.get('subscriberCount', 0))
                
                # Rough heuristic: highly active users have higher views/videos. Or we just fetch liked videos.
                # Let's fetch liked videos count to estimate watch time
                liked_res = requests.get(
                    f"{self.BASE}/youtube/v3/videos?myRating=like&part=snippet&maxResults=50",
                    headers=self.headers, timeout=8
                ).json()
                
                liked_count = len(liked_res.get('items', []))
                
                # Estimate: if they like a lot, they watch a lot. 50+ likes = ~120 hours/month.
                estimated_hours = 30 + (liked_count * 1.5)
                
                return {
                    'estimated_hours_month': min(150, estimated_hours), # cap at 150
                    'liked_recent': liked_count
                }
            return None
        except Exception:
            return None

    def _gmail_stats(self) -> dict:
        try:
            # Profile (total message count + storage)
            profile = requests.get(
                f"{self.BASE}/gmail/v1/users/me/profile",
                headers=self.headers, timeout=8
            ).json()
            total_msgs = profile.get('messagesTotal', 0)
            threads = profile.get('threadsTotal', 0)

            # Count messages in last 30 days via list API
            since = (datetime.utcnow() - timedelta(days=30)).strftime('%Y/%m/%d')
            sent_res = requests.get(
                f"{self.BASE}/gmail/v1/users/me/messages",
                headers=self.headers,
                params={'q': f'after:{since} in:sent', 'maxResults': 1},
                timeout=8
            ).json()
            recv_res = requests.get(
                f"{self.BASE}/gmail/v1/users/me/messages",
                headers=self.headers,
                params={'q': f'after:{since} in:inbox', 'maxResults': 1},
                timeout=8
            ).json()
            spam_res = requests.get(
                f"{self.BASE}/gmail/v1/users/me/messages",
                headers=self.headers,
                params={'q': f'after:{since} in:spam', 'maxResults': 1},
                timeout=8
            ).json()

            # Storage from Drive quota (Gmail contributes)
            quota = requests.get(
                f"{self.BASE}/drive/v3/about?fields=storageQuota",
                headers=self.headers, timeout=8
            ).json()
            usage_bytes = int(quota.get('storageQuota', {}).get('usageInDrive', 0))
            storage_gb = round(usage_bytes / (1024**3), 2)

            return {
                'emails_sent_30d': sent_res.get('resultSizeEstimate', 0),
                'emails_received_30d': recv_res.get('resultSizeEstimate', 0),
                'spam_count': spam_res.get('resultSizeEstimate', 0),
                'storage_gb': storage_gb,
                'total_messages': total_msgs,
            }
        except Exception as e:
            return self._gmail_fallback()

    def _gmail_fallback(self) -> dict:
        """Conservative estimates when API call fails."""
        return {
            'emails_sent_30d': 150,
            'emails_received_30d': 800,
            'spam_count': 200,
            'storage_gb': 5.0,
            'total_messages': 5000,
            '_estimated': True
        }

    def _drive_stats(self) -> dict:
        try:
            about = requests.get(
                f"{self.BASE}/drive/v3/about?fields=storageQuota",
                headers=self.headers, timeout=8
            ).json()
            sq = about.get('storageQuota', {})
            total_bytes = int(sq.get('usage', 0))
            total_gb = round(total_bytes / (1024**3), 2)

            # Count files
            files_res = requests.get(
                f"{self.BASE}/drive/v3/files",
                headers=self.headers,
                params={'pageSize': 1, 'fields': 'nextPageToken,files(id)'},
                timeout=8
            ).json()
            # Approximate file count from page token presence
            file_count_est = 500 if files_res.get('nextPageToken') else len(files_res.get('files', []))

            # Shared files count
            shared_res = requests.get(
                f"{self.BASE}/drive/v3/files",
                headers=self.headers,
                params={'q': 'sharedWithMe=true', 'pageSize': 1, 'fields': 'nextPageToken'},
                timeout=8
            ).json()
            shared_est = 50 if shared_res.get('nextPageToken') else 10

            return {
                'total_storage_gb': total_gb,
                'files_count': file_count_est,
                'shared_files': shared_est,
                'large_files_gb': round(total_gb * 0.5, 2),  # estimate: 50% is large files
            }
        except Exception:
            return {
                'total_storage_gb': 10.0,
                'files_count': 300,
                'shared_files': 30,
                'large_files_gb': 5.0,
                '_estimated': True
            }

    def _device_estimates(self) -> list:
        """
        We can't read hardware from a web app.
        Return sensible defaults; user can adjust in UI.
        """
        return [
            {
                'name': 'Primary device',
                'type': 'laptop',
                'screen_hours_day': 7,
                'video_hours_day': 2,
                'cloud_sync_gb_month': 3.0,
                '_estimated': True
            },
            {
                'name': 'Mobile device',
                'type': 'phone',
                'screen_hours_day': 4,
                'video_hours_day': 1.5,
                'cloud_sync_gb_month': 1.5,
                '_estimated': True
            }
        ]

    def _streaming_estimate(self) -> dict:
        """Streaming data can't be pulled from Google APIs — use averages."""
        return {
            'video_hours_month': 90,
            'audio_hours_month': 40,
            'video_quality': 'HD',
            '_estimated': True
        }

    def _search_estimate(self) -> dict:
        return {
            'searches_day': 25,
            'ai_queries_month': 50,
            '_estimated': True
        }
