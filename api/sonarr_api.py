"""
Sonarr API client for checking existing episodes
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)


class SonarrAPI:
    """Sonarr API client for checking existing episodes"""

    def __init__(self, base_url=None, api_key=None):
        raw_url = base_url or os.environ.get('sonarr_applicationurl', '')
        self.base_url = raw_url.rstrip('/') if raw_url else ''
        self.api_key = api_key or os.environ.get('sonarr_apikey', '')
        self.session = requests.Session()
        self.session.headers.update({'X-Api-Key': self.api_key})

    def get_series_episodes(self, series_id):
        """Get all episodes for a series"""
        try:
            url = f"{self.base_url}/api/v3/episode"
            params = {'seriesId': series_id}
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to get episodes from Sonarr: {e}")
            return []

    def get_series_by_title(self, title):
        """Find series by title"""
        try:
            url = f"{self.base_url}/api/v3/series"
            response = self.session.get(url)
            response.raise_for_status()
            series_list = response.json()

            # Find series with matching title
            for series in series_list:
                if series['title'].lower() == title.lower():
                    return series
            return None
        except Exception as e:
            logger.warning(f"Failed to get series from Sonarr: {e}")
            return None

    def get_existing_episodes(self, series_title, season_number=None):
        """Get list of existing episode codes (S01E01 format)"""
        existing_episodes = set()

        try:
            series = self.get_series_by_title(series_title)
            if not series:
                logger.warning(f"Series '{series_title}' not found in Sonarr")
                return existing_episodes

            episodes = self.get_series_episodes(series['id'])
            for episode in episodes:
                if episode.get('hasFile', False):
                    season_num = episode.get('seasonNumber', 0)
                    episode_num = episode.get('episodeNumber', 0)
                    episode_code = f"S{season_num:02d}E{episode_num:02d}"
                    existing_episodes.add(episode_code)

            logger.info(f"Found {len(existing_episodes)} existing episodes in Sonarr: {sorted(existing_episodes)}")
        except Exception as e:
            logger.warning(f"Error checking existing episodes: {e}")

        return existing_episodes