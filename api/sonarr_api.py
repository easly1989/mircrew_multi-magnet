"""
Sonarr API client for checking existing episodes
"""

import os
import logging
import requests
import re
import time

logger = logging.getLogger(__name__)


def normalize_title(title):
    """Normalize series title to match Sonarr's storage format"""
    if not title:
        return title
    # Remove extra spaces and normalize
    title = re.sub(r'\s+', ' ', title.strip())
    # Remove special characters that Sonarr might ignore
    title = re.sub(r'[^\w\s]', '', title)
    return title


def retry_api_call(max_retries=3, delay=1):
    """Decorator for retrying API calls with exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        raise e
                    logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(delay * (2 ** attempt))
        return wrapper
    return decorator


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
        url = f"{self.base_url}/api/v3/episode"
        params = {'seriesId': series_id}
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                episodes = response.json()
                logger.debug(f"Retrieved {len(episodes)} episodes for series {series_id}")
                logger.debug(f"Episodes sample: {episodes[:3] if episodes else 'None'}")
                return episodes
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    logger.warning(f"Failed to get episodes from Sonarr after retries: {e}")
                    return []
                logger.warning(f"API call failed (attempt {attempt + 1}/3): {e}")
                time.sleep(1 * (2 ** attempt))
        return []

    def get_series_by_title(self, title):
        """Find series by title"""
        normalized_title = normalize_title(title)
        url = f"{self.base_url}/api/v3/series"
        for attempt in range(3):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                series_list = response.json()
                logger.debug(f"Retrieved {len(series_list)} series from Sonarr")

                # Find series with matching normalized title
                for series in series_list:
                    series_normalized = normalize_title(series['title'])
                    if series_normalized.lower() == normalized_title.lower():
                        logger.info(f"Found matching series: '{series['title']}' for input '{title}'")
                        return series
                logger.warning(f"Series '{title}' (normalized: '{normalized_title}') not found in Sonarr")
                logger.debug(f"Available series titles: {[s['title'] for s in series_list[:5]]}")
                return None
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    logger.warning(f"Failed to get series from Sonarr after retries: {e}")
                    return None
                logger.warning(f"API call failed (attempt {attempt + 1}/3): {e}")
                time.sleep(1 * (2 ** attempt))
        return None

    def find_matching_release(self, extractor, release_title, series_title=None, season=None, episode=None):
        """Find matching forum release using metadata-aware search"""
        if not extractor or not release_title:
            logger.warning("Missing extractor or release_title for find_matching_release")
            return None

        try:
            logger.info(f"Finding matching release for: {release_title}")
            if series_title:
                logger.debug(f"Series context: {series_title}")
            if season:
                logger.debug(f"Season context: {season}")
            if episode:
                logger.debug(f"Episode context: {episode}")

            # Try enhanced metadata-aware search first
            enhanced_search_method = getattr(extractor, 'search_thread_by_release_title_with_metadata', None)
            if enhanced_search_method and (series_title or season or episode):
                logger.info("Using enhanced metadata-aware search")
                thread_url = enhanced_search_method(
                    release_title=release_title,
                    series_title=series_title,
                    season=season,
                    episode=episode
                )
                if thread_url:
                    logger.info("Enhanced search successful")
                    return thread_url

            # Fallback to standard search
            logger.info("Enhanced search failed or insufficient metadata, using standard search")
            fallback_method = getattr(extractor, 'search_thread_by_release_title', None)
            if fallback_method:
                thread_url = fallback_method(release_title)
                if thread_url:
                    logger.info("Standard search successful")
                    return thread_url

            # Last resort: use new search_thread method with caching
            logger.info("Standard search failed, using cached search_thread method")
            search_thread_method = getattr(extractor, 'search_thread', None)
            if search_thread_method:
                thread_url = search_thread_method(release_title)
                if thread_url:
                    logger.info("Cached search successful")
                    return thread_url

            logger.warning("All search methods failed to find matching release")
            return None

        except Exception as e:
            logger.error(f"Error in find_matching_release: {e}")
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
            file_count = 0
            total_episodes = len(episodes)
            for episode in episodes:
                has_file = episode.get('hasFile', False)
                season_num = episode.get('seasonNumber', 0)
                episode_num = episode.get('episodeNumber', 0)
                if has_file:
                    episode_code = f"S{season_num:02d}E{episode_num:02d}"
                    existing_episodes.add(episode_code)
                    file_count += 1
                    logger.debug(f"Existing episode: {episode_code} (season {season_num}, ep {episode_num})")

            logger.info(f"Sonarr API check complete: {file_count} episodes with files out of {total_episodes} total episodes")
            if existing_episodes:
                logger.info(f"Existing episodes: {sorted(existing_episodes)}")
            else:
                logger.warning("No episodes with files found in Sonarr")
        except Exception as e:
            logger.warning(f"Error checking existing episodes: {e}")

        return existing_episodes