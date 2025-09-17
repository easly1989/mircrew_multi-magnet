#!/usr/bin/env python3
"""
MIRCrew Forum Extractor Implementation
Concrete implementation of ForumExtractor for MIRCrew forum.
"""

import re
import requests
import time
import random
import logging
import pickle
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, parse_qs, urlparse, unquote, quote_plus
import sys
import os
import yaml
from datetime import datetime, timedelta
from typing import Optional, List, Dict
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.forum_extractor import ForumExtractor
from torrents.torrent_client import TorrentClient

# Setup logging
logger = logging.getLogger(__name__)

# Configuration constants
MIRCREW_BASE_URL = str(os.environ.get('MIRCREW_BASE_URL', 'https://mircrew-releases.org/'))
MIRCREW_USERNAME = str(os.environ.get('MIRCREW_USERNAME'))
MIRCREW_PASSWORD = str(os.environ.get('MIRCREW_PASSWORD'))

# Cookie persistence
COOKIE_FILE = "mircrew_cookies.pkl"

# Validate required MIRCrew environment variables
if not MIRCREW_USERNAME or not MIRCREW_PASSWORD:
    raise ValueError("Missing required MIRCrew environment variables. Please check .env file.")

# Type assertions for mypy/pylance
assert MIRCREW_USERNAME is not None
assert MIRCREW_PASSWORD is not None


def extract_magnet_title_from_url(magnet_url):
    """Extracts the speaking title from the dn parameter of the magnet link"""
    parsed = urlparse(magnet_url)
    params = parse_qs(parsed.query)
    dn_list = params.get('dn', [])
    if dn_list:
        title = unquote(dn_list[0])
        # Remove common file extensions (.mkv, .mp4, .avi, .m4v, .mov)
        title = re.sub(r'\.(mkv|mp4|avi|m4v|mov)$', '', title, flags=re.IGNORECASE)
        return title
    return ''


class MIRCrewExtractor(ForumExtractor):
    """MIRCrew forum extractor implementation"""

    def __init__(self, torrent_client: TorrentClient):
        super().__init__(torrent_client)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Thread ID cache attributes
        self.cache_file = "mircrew_cache.yml"
        self.thread_id_cache = {}
        self.cache_loaded = False

        # Cache metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_last_metrics_log = None
        self.cache_max_size = 100

        self.load_cookies()
        self.load_cache()

    def load_cookies(self):
        """Load saved cookies from file"""
        try:
            if os.path.exists(COOKIE_FILE):
                with open(COOKIE_FILE, 'rb') as f:
                    cookies = pickle.load(f)
                    self.session.cookies.update(cookies)
                logger.debug("Cookies loaded from file")
        except Exception as e:
            logger.warning(f"Error loading cookies: {e}")

    def save_cookies(self):
        """Save current cookies to file"""
        try:
            with open(COOKIE_FILE, 'wb') as f:
                pickle.dump(self.session.cookies, f)
            logger.debug("Cookies saved to file")
        except Exception as e:
            logger.warning(f"Error saving cookies: {e}")

    def load_cache(self):
        """Load thread ID cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = yaml.safe_load(f)
                    if cache_data and 'thread_cache' in cache_data:
                        loaded_cache = cache_data['thread_cache']
                        # Convert legacy format to new format for backward compatibility
                        for key, value in loaded_cache.items():
                            if isinstance(value, str):
                                # Legacy format - convert to new format
                                loaded_cache[key] = {
                                    'thread_id': value,
                                    'timestamp': datetime.now().isoformat()  # Use current time for legacy entries
                                }
                            elif isinstance(value, dict) and 'thread_id' not in value:
                                # Malformed entry - fix it
                                if isinstance(value, dict):
                                    loaded_cache[key] = {
                                        'thread_id': str(value),
                                        'timestamp': datetime.now().isoformat()
                                    }
                        self.thread_id_cache = loaded_cache
                        logger.debug(f"Loaded {len(self.thread_id_cache)} cached thread IDs")
                    else:
                        self.thread_id_cache = {}
                self.cache_loaded = True
            else:
                self.thread_id_cache = {}
                self.cache_loaded = True
                logger.debug("Cache file not found, starting with empty cache")
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
            self.thread_id_cache = {}
            self.cache_loaded = True

    def save_cache(self):
        """Save thread ID cache to file"""
        try:
            # Convert cache entries to saveable format
            saveable_cache = {}
            for key, value in self.thread_id_cache.items():
                if isinstance(value, dict):
                    saveable_cache[key] = value
                else:
                    # Legacy format - convert to new format
                    saveable_cache[key] = {
                        'thread_id': str(value),
                        'timestamp': datetime.now().isoformat()
                    }

            cache_data = {'thread_cache': saveable_cache}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                yaml.dump(cache_data, f, default_flow_style=False, allow_unicode=True)
            logger.debug(f"Saved {len(self.thread_id_cache)} thread IDs to cache")
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")

    def get_cached_thread_id(self, series_title, season):
        """Get cached thread ID for series and season"""
        if not self.cache_loaded:
            self.load_cache()

        if not series_title or not season:
            return None

        # Normalize season format
        try:
            season_num = int(season)
            cache_key = f"{series_title} S{season_num:02d}"
        except (ValueError, TypeError):
            cache_key = f"{series_title} S{season}"

        cache_entry = self.thread_id_cache.get(cache_key)
        if cache_entry:
            # Handle both new format (dict) and legacy format (string)
            if isinstance(cache_entry, dict):
                thread_id = cache_entry.get('thread_id')
                # Check if entry has expired
                if 'timestamp' in cache_entry:
                    try:
                        entry_date = datetime.fromisoformat(cache_entry['timestamp'])
                        if entry_date < datetime.now() - timedelta(days=180):
                            logger.debug(f"Cache entry expired for '{cache_key}'")
                            del self.thread_id_cache[cache_key]
                            self.cache_misses += 1
                            self._log_cache_metrics()
                            return None
                    except (ValueError, TypeError):
                        logger.debug(f"Invalid timestamp for '{cache_key}', treating as expired")
                        del self.thread_id_cache[cache_key]
                        self.cache_misses += 1
                        self._log_cache_metrics()
                        return None
            else:
                # Legacy format - treat as string thread_id
                thread_id = cache_entry

            if thread_id:
                self.cache_hits += 1
                logger.debug(f"Cache hit for '{cache_key}': thread {thread_id}")
                self._log_cache_metrics()
                return str(thread_id)

        self.cache_misses += 1
        logger.debug(f"Cache miss for '{cache_key}'")
        self._log_cache_metrics()
        return None

    def _log_cache_metrics(self):
        """Log cache hit rate metrics periodically"""
        total_lookups = self.cache_hits + self.cache_misses
        if total_lookups == 0:
            return

        # Log metrics every 10 lookups or if it's been more than 5 minutes since last log
        current_time = datetime.now()
        should_log = (total_lookups % 10 == 0 or
                     self.cache_last_metrics_log is None or
                     (current_time - self.cache_last_metrics_log).total_seconds() > 300)

        if should_log:
            hit_rate = (self.cache_hits / total_lookups) * 100
            logger.info(f"Cache metrics - Hits: {self.cache_hits}, Misses: {self.cache_misses}, "
                       f"Total: {total_lookups}, Hit Rate: {hit_rate:.1f}%")
            self.cache_last_metrics_log = current_time

    def _manage_cache_size(self):
        """Manage cache size by evicting old entries if cache exceeds maximum size"""
        # Clean expired entries first
        self._clean_expired_entries()

        # If still over limit, evict oldest entries (LRU-style)
        if len(self.thread_id_cache) >= self.cache_max_size:
            # Sort by timestamp and keep only the most recent entries
            sorted_entries = sorted(
                self.thread_id_cache.items(),
                key=lambda x: datetime.fromisoformat(x[1]['timestamp']) if isinstance(x[1], dict) else datetime.min,
                reverse=True
            )
            # Keep only the most recent 80% of max size to leave room for new entries
            keep_count = int(self.cache_max_size * 0.8)
            entries_to_keep = dict(sorted_entries[:keep_count])
            removed_count = len(self.thread_id_cache) - len(entries_to_keep)
            if removed_count > 0:
                logger.info(f"Cache size management: removed {removed_count} old entries")
            self.thread_id_cache = entries_to_keep

    def _clean_expired_entries(self):
        """Remove entries that have expired (older than 6 months)"""
        cutoff_date = datetime.now() - timedelta(days=180)  # 6 months
        expired_keys = []

        for key, value in self.thread_id_cache.items():
            if isinstance(value, dict) and 'timestamp' in value:
                try:
                    entry_date = datetime.fromisoformat(value['timestamp'])
                    if entry_date < cutoff_date:
                        expired_keys.append(key)
                except (ValueError, TypeError):
                    # If timestamp is malformed, treat as expired
                    expired_keys.append(key)
            else:
                # Legacy format without timestamp - treat as expired to force refresh
                expired_keys.append(key)

        for key in expired_keys:
            del self.thread_id_cache[key]

        if expired_keys:
            logger.info(f"Cleaned {len(expired_keys)} expired cache entries")

    def cache_thread_id(self, series_title, season, thread_id):
        """Cache thread ID for series and season"""
        if not series_title or not season or not thread_id:
            return

        # Normalize season format
        try:
            season_num = int(season)
            cache_key = f"{series_title} S{season_num:02d}"
        except (ValueError, TypeError):
            cache_key = f"{series_title} S{season}"

        # Check cache size and evict if necessary
        self._manage_cache_size()

        # Add entry with timestamp
        self.thread_id_cache[cache_key] = {
            'thread_id': str(thread_id),
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"Cached thread ID for '{cache_key}': {thread_id}")

        # Save cache immediately for persistence
        self.save_cache()

    def login(self, retries=15, initial_wait=5):
        """Login to MIRCrew, returns sid if ok, False if fails"""
        # Check if already logged in first
        if self.is_already_logged_in():
            logger.info("Already authenticated on MIRCrew")
            # Try to get existing SID
            for cookie in self.session.cookies:
                if "sid" in cookie.name:
                    return cookie.value
            return True

        def is_logged_in(soup):
            """Check if user is logged in based on page content"""
            # Check for login failure indicators first
            error_indicators = [
                soup.find(string=re.compile(r'(?i)login.*failed|invalid.*credentials|wrong.*password|access.*denied')),
                soup.find('div', {'class': re.compile(r'error|alert')}, string=re.compile(r'(?i)login|password')),
                soup.find('form', {'id': 'login'})  # Still showing login form indicates failure
            ]

            if any(error_indicators):
                logger.debug("Login failure indicators found on page")
                return False

            # Check for success indicators
            success_indicators = [
                soup.find('a', {'href': re.compile(r'mode=logout')}),
                soup.find('a', {'href': re.compile(r'logout')}),
                soup.find('a', string=re.compile(r'(?i)logout|esci|log out')),
                soup.find(['span', 'div', 'a'], string=re.compile(f'(?i){re.escape(MIRCREW_USERNAME)}')),
                soup.find('strong', string=re.compile(f'(?i){re.escape(MIRCREW_USERNAME)}')),
                soup.find(string=re.compile(r'(?i)welcome.*back|benvenuto|logged.*in')),
                soup.find('div', {'class': re.compile(r'user.*panel|welcome')}),
                soup.find('li', {'class': 'user-info'})
            ]

            logged_in = any(success_indicators)
            logger.debug(f"Login verification: {len([x for x in success_indicators if x])} success indicators found")
            return logged_in

        for attempt in range(retries):
            try:
                # Exponential backoff with jitter for retries
                if attempt > 0:
                    wait_time = min(initial_wait * (2 ** (attempt - 1)), 300)  # Cap at 5 minutes
                    jitter = random.uniform(0.5, 1.5)  # Add some randomness
                    actual_wait = wait_time * jitter
                    logger.info(f"Retrying login in {actual_wait:.1f} seconds... (attempt {attempt+1}/{retries})")
                    time.sleep(actual_wait)

                login_url = urljoin(MIRCREW_BASE_URL, "ucp.php?mode=login")
                logger.info(f"Login attempt {attempt+1}/{retries}")

                # Get login form with timeout and retry on failure
                try:
                    resp = self.session.get(login_url, timeout=30)
                    resp.raise_for_status()
                except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                    logger.warning(f"Error requesting login form: {e}")
                    if attempt == retries - 1:
                        logger.error("Unable to get login form after all attempts")
                        return False
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                form = soup.find('form', {'id': 'login'})
                if not form or not isinstance(form, Tag):
                    logger.error("Login form not found on page")
                    if attempt == retries - 1:
                        return False
                    continue

                form_action = str(form.attrs.get('action', login_url))
                if not form_action.startswith('http'):
                    form_action = urljoin(MIRCREW_BASE_URL, form_action)

                login_data = {}
                for input_tag in form.find_all('input'):
                    if not isinstance(input_tag, Tag):
                        continue
                    name = input_tag.attrs.get('name')
                    if name:
                        input_type = str(input_tag.attrs.get('type', 'text')).lower()
                        if input_type == 'checkbox':
                            if input_tag.attrs.get('checked'):
                                login_data[name] = input_tag.attrs.get('value', 'on')
                        else:
                            login_data[name] = input_tag.attrs.get('value', '')

                login_data.update({
                    'username': MIRCREW_USERNAME,
                    'password': MIRCREW_PASSWORD,
                    'login': 'Login',
                    'redirect': './index.php'
                })

                logger.debug(f"Submitting login to: {form_action}")

                # Submit login with timeout and retry on failure
                try:
                    resp = self.session.post(form_action, data=login_data, allow_redirects=True, timeout=30)
                    logger.info(f"Login POST status: {resp.status_code}, URL finale: {resp.url}")
                except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                    logger.warning(f"Error sending login data: {e}")
                    if attempt == retries - 1:
                        logger.error("Unable to send login data after all attempts")
                        return False
                    continue

                if resp.status_code not in (200, 302):
                    logger.warning(f"Login POST failed with status {resp.status_code}")
                    if attempt == retries - 1:
                        return False
                    continue

                # Check if login succeeded
                soup = BeautifulSoup(resp.text, 'html.parser')

                if is_logged_in(soup):
                    # Try to get session ID from cookies
                    sid = None
                    for cookie in self.session.cookies:
                        if "sid" in cookie.name:
                            sid = cookie.value
                            break

                    # Save cookies for future sessions
                    self.save_cookies()

                    if sid:
                        logger.info(f"Login successful with SID: {sid[:8]}...")
                    else:
                        logger.info("Login successful (no SID found)")

                    return sid or True
                else:
                    logger.warning(f"Login attempt {attempt+1} failed - checking page...")

                    # Log some debug info about what was found
                    error_text = soup.find(string=re.compile(r'(?i)error|failed|wrong|invalid'))
                    if error_text:
                        error_str = str(error_text).strip()
                        logger.warning(f"Possible error found on page: {error_str[:100]}...")

                    if attempt == retries - 1:
                        logger.error("Login failed after all attempts")
                        return False

            except Exception as e:
                logger.error(f"Unexpected error in login attempt {attempt+1}: {e}")
                if attempt == retries - 1:
                    logger.error("Login failed due to repeated errors")
                    return False

        return False

    def is_already_logged_in(self):
        """Check if user is already logged in by visiting the index page"""
        try:
            index_url = urljoin(MIRCREW_BASE_URL, "index.php")
            resp = self.session.get(index_url, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Check for login form - if present, not logged in
            if soup.find('form', {'id': 'login'}):
                logger.debug("Login form found - not logged in")
                return False

            # Check for logout link or username - indicates logged in
            logout_links = soup.find_all('a', {'href': re.compile(r'(mode=logout|logout)')})
            username_elements = soup.find_all(['span', 'div', 'a'], string=re.compile(f'(?i){re.escape(MIRCREW_USERNAME)}'))

            if logout_links or username_elements:
                logger.debug("Logout link or username found - already logged in")
                return True

            logger.debug("Unable to determine login status from index page")
            return False

        except Exception as e:
            logger.warning(f"Error checking login status: {e}")
            return False

    def verify_session(self):
        """Verify if the session is still valid"""
        try:
            # First try a quick check by visiting index
            if self.is_already_logged_in():
                return True

            # Fallback to the original method
            test_url = urljoin(MIRCREW_BASE_URL, "ucp.php?mode=login")
            resp = self.session.get(test_url, allow_redirects=False, timeout=30)

            if resp.status_code == 302 and "login" in resp.headers.get('Location', ''):
                logger.warning("Session expired - redirecting to login")
                return False

            # If we get here without redirect, check the page content
            soup = BeautifulSoup(resp.text, 'html.parser')
            if soup.find('form', {'id': 'login'}):
                logger.warning("Session expired - login form present")
                return False

            return True
        except Exception as e:
            logger.warning(f"Error verifying session: {e}")
            return False

    def extract_thread_id_from_url(self, url: str) -> Optional[str]:
        """Extract thread ID from MIRCrew forum URL"""
        if not url:
            return None

        # Handle both absolute and relative URLs
        if url.startswith('http'):
            parsed = urlparse(url)
            path = parsed.path
            query = parsed.query
        else:
            path = url
            query = ''

        # Extract thread ID from various URL patterns
        patterns = [
            r'viewtopic\.php\?f=\d+&t=(\d+)',  # viewtopic.php?f=52&t=12345
            r't=(\d+)',                         # t=12345 parameter
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                thread_id = match.group(1)
                logger.debug(f"Extracted thread ID '{thread_id}' from URL: {url}")
                return thread_id

        logger.warning(f"Could not extract thread ID from URL: {url}")
        return None

    def search_thread_by_release_title_with_metadata(self, release_title, series_title=None, season=None, episode=None):
        """Enhanced search using Sonarr metadata for more precise matching"""
        if not self.verify_session():
            logger.warning("Session expired, attempting re-login...")
            if not self.login():
                logger.error("Re-login failed")
                return None
            logger.info("Re-login successful, continuing search...")

        # Strategy 1: Use release title with enhanced metadata
        logger.info(f"Searching for: {release_title}")
        if series_title:
            logger.info(f"Series context: {series_title}")
        if season and episode:
            logger.info(f"Episode context: S{season}E{episode}")

        # Try multiple search strategies with increasing specificity
        search_strategies = self._build_enhanced_search_queries(release_title, series_title, season, episode)

        for strategy_name, query in search_strategies:
            logger.info(f"Trying {strategy_name}: {query}")
            encoded_query = quote_plus(f'"{query}"')
            thread_url = self._perform_search(encoded_query)

            if thread_url:
                logger.info(f"Found thread using {strategy_name}")
                return thread_url

        logger.warning("No thread found with any enhanced search strategy")
        return None

    def _build_enhanced_search_queries(self, release_title, series_title=None, season=None, episode=None):
        """Build multiple search queries with increasing specificity using available metadata"""
        queries = []

        # Strategy 1: Exact release title match (most specific)
        queries.append(("exact_title", release_title))

        # Strategy 2: Clean release title (remove extra metadata)
        clean_title = self._clean_release_title_for_search(release_title)
        if clean_title != release_title:
            queries.append(("clean_title", clean_title))

        # Strategy 3: Series + Season + Episode (if available)
        if series_title and season and episode:
            season_episode = f"S{int(season):02d}E{int(episode):02d}"
            query = f"{series_title} {season_episode}"
            queries.append(("series_season_ep", query))

            # Also try Italian format
            italian_se = f"Stagione {season} Episodio {episode}"
            query_it = f"{series_title} {italian_se}"
            queries.append(("series_season_ep_it", query_it))

        # Strategy 4: Series + Season only
        elif series_title and season:
            query = f"{series_title} Stagione {season}"
            queries.append(("series_season", query))

            # Also try English format
            query_en = f"{series_title} Season {season}"
            queries.append(("series_season_en", query_en))

        # Strategy 5: Just series title
        elif series_title:
            queries.append(("series_only", series_title))

        # Strategy 6: Extract and use metadata from release title
        metadata_queries = self._extract_enhanced_search_queries(release_title)
        for query_type, query in metadata_queries:
            queries.append((f"metadata_{query_type}", query))

        return queries

    def _clean_release_title_for_search(self, title):
        """Clean release title by removing common unwanted metadata"""
        # Remove file extensions
        title = re.sub(r'\.(mkv|mp4|avi|m4v|mov)$', '', title, flags=re.IGNORECASE)

        # Remove quality/resolution info that might interfere with search
        title = re.sub(r'\b(1080p|720p|2160p|4K|UHD|BluRay|WEB-DL|HDTV)\b', '', title, flags=re.IGNORECASE)

        # Remove common release group patterns
        title = re.sub(r'-\w+$', '', title)

        # Clean up extra spaces
        title = re.sub(r'\s+', ' ', title).strip()

        return title

    def search_thread_by_id(self, thread_id: str):
        """Directly access a thread by its ID for maximum reliability"""
        if not thread_id:
            logger.warning("No thread ID provided")
            return None

        if not self.verify_session():
            logger.warning("Session expired, attempting re-login...")
            if not self.login():
                logger.error("Re-login failed")
                return None
            logger.info("Re-login successful")

        thread_url = f"{MIRCREW_BASE_URL}viewtopic.php?f=51&t={thread_id}"
        logger.info(f"Using direct thread access: {thread_url}")

        # Verify the thread exists by making a quick request
        try:
            response = self.session.get(thread_url, timeout=30)
            if response.status_code == 200 and "viewtopic.php" in response.url:
                logger.info(f"Thread {thread_id} exists and is accessible")
                return thread_url
            else:
                logger.warning(f"Thread {thread_id} not found or not accessible")
                return None
        except Exception as e:
            logger.error(f"Error verifying thread {thread_id}: {e}")
            return None

    def search_thread_by_release_title(self, release_title):
        """Search thread by release title using the existing session with enhanced fallback strategies"""
        """Search thread by release title using the existing session with enhanced fallback strategies"""
        if not self.verify_session():
            logger.warning("Session expired, attempting re-login...")
            if not self.login():
                logger.error("Re-login failed")
                return None
            logger.info("Re-login successful, continuing search...")

        base_search_url = urljoin(MIRCREW_BASE_URL, "search.php")

        # Strategy 1: Exact match with full title
        logger.info(f"Searching for exact match: {release_title}")
        encoded_query = quote_plus(f"\"{release_title}\"")
        thread_url = self._perform_search(encoded_query)

        if thread_url:
            logger.info("Found thread with exact match")
            return thread_url

        # Strategy 2: Enhanced metadata-aware search
        logger.info("Exact match failed, trying enhanced metadata search...")
        enhanced_queries = self._extract_enhanced_search_queries(release_title)

        for query_type, query in enhanced_queries:
            logger.info(f"Trying {query_type}: {query}")
            encoded_query = quote_plus(f"\"{query}\"")
            thread_url = self._perform_search(encoded_query)
            if thread_url:
                logger.info(f"Found thread with {query_type}")
                return thread_url

        # Strategy 3: Season-level fallback (original method)
        logger.info("Enhanced searches failed, trying season-level search...")
        season_query = self._extract_season_search_query(release_title)
        if season_query:
            logger.info(f"Searching for season-level: {season_query}")
            encoded_query = quote_plus(f"\"{season_query}\"")
            thread_url = self._perform_search(encoded_query)
            if thread_url:
                logger.info("Found thread with season-level search")
                return thread_url

        logger.warning("No thread found with any search strategy")
        return None

    def search_thread(self, query):
        """Search thread with caching support - checks cache first, then falls back to forum search"""
        if not query:
            logger.warning("No query provided for search_thread")
            return None

        # Extract series metadata from query for cache lookup
        series_title = self._extract_base_series_name(query)
        season = self._extract_season_number(query)

        # Try cache lookup first
        if series_title and season:
            cached_thread_id = self.get_cached_thread_id(series_title, season)
            if cached_thread_id:
                logger.info(f"Using cached thread ID {cached_thread_id} for {series_title} S{season}")
                thread_url = self.search_thread_by_id(cached_thread_id)
                if thread_url:
                    return thread_url
                else:
                    logger.warning(f"Cached thread ID {cached_thread_id} no longer valid, removing from cache")
                    # Remove invalid cache entry
                    try:
                        season_num = int(season)
                        cache_key = f"{series_title} S{season_num:02d}"
                        if cache_key in self.thread_id_cache:
                            del self.thread_id_cache[cache_key]
                            self.save_cache()
                    except (ValueError, TypeError):
                        pass

        # Cache miss or no metadata available - fallback to forum search
        logger.info("Cache miss or insufficient metadata, performing forum search...")
        encoded_query = quote_plus(f'"{query}"')
        thread_url = self._perform_search(encoded_query)

        # Cache the result if we found a thread and have metadata
        if thread_url and series_title and season:
            thread_id = self.extract_thread_id_from_url(thread_url)
            if thread_id:
                self.cache_thread_id(series_title, season, thread_id)
                logger.info(f"Cached new thread ID {thread_id} for {series_title} S{season}")

        return thread_url

    def _perform_search(self, encoded_query):
        """Perform the actual search with given query and return detailed results"""
        params = {
            "keywords": f"{encoded_query}",
            "terms": "all",
            "author": "",
            "fid[]": ["28", "51", "52", "30"],
            "sc": "1",
            "sf": "titleonly",
            "sr": "topics",
            "sk": "t",
            "sd": "d",
            "st": "0",
            "ch": "300",
            "t": "0",
            "submit": "Cerca"
        }

        try:
            request_text = f"https://mircrew-releases.org/search.php?keywords={encoded_query}&terms=all&author=&fid%5B%5D=28&fid%5B%5D=51&fid%5B%5D=52&fid%5B%5D=30&sc=1&sf=titleonly&sr=topics&sk=t&sd=d&st=0&ch=300&t=0&submit=Cerca"

            response = self.session.get(request_text)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"HTTP error during search on MIRCrew: {e}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        search_results_container = soup.find('ul', {'class': 'topiclist topics'})
        if not search_results_container or not isinstance(search_results_container, Tag):
            logger.warning("Search results container not found (ul.topiclist.topics)")
            return None

        logger.info("Search results container found, searching for thread...")

        # Collect all potential thread results for better matching
        thread_results = []

        for row in search_results_container.find_all('li', {'class': 'row'}):
            if not isinstance(row, Tag):
                continue

            # Find the topic title link
            topic_link = row.find('a', {'class': 'topictitle'})
            if not topic_link or not isinstance(topic_link, Tag):
                continue

            href = topic_link.attrs.get('href')
            if not href:
                continue

            href_str = str(href)
            if "viewtopic.php" not in href_str:
                continue

            # Build full URL
            if href_str.startswith('http'):
                thread_url = href_str
            else:
                thread_url = urljoin(MIRCREW_BASE_URL, href_str)

            # Extract thread title for matching
            thread_title = topic_link.get_text().strip()

            # Extract thread ID
            thread_id = self.extract_thread_id_from_url(thread_url)

            thread_info = {
                'url': thread_url,
                'title': thread_title,
                'thread_id': thread_id,
                'score': 0  # Will be used for ranking results
            }

            thread_results.append(thread_info)
            logger.debug(f"Found thread: {thread_title} (ID: {thread_id})")

        if not thread_results:
            logger.warning("No MIRCrew threads found in search.")
            return None

        # Return the first (most relevant) result
        best_result = thread_results[0]
        logger.info(f"MIRCrew thread found: {best_result['title']} (ID: {best_result['thread_id']})")
        return best_result['url']

    def _extract_enhanced_search_queries(self, release_title):
        """Extract multiple enhanced search queries from release title including metadata"""
        queries = []

        try:
            # Extract base series name (remove season/episode info)
            base_title = self._extract_base_series_name(release_title)

            if not base_title:
                return queries

            # Extract metadata components
            resolution = self._extract_resolution(release_title)
            codec = self._extract_codec(release_title)
            year = self._extract_year(release_title)
            season_num = self._extract_season_number(release_title)

            # Strategy 1: Series + Season + Resolution + Codec
            if season_num and (resolution or codec):
                metadata_parts = []
                if resolution:
                    metadata_parts.append(resolution)
                if codec:
                    metadata_parts.append(codec)

                if metadata_parts:
                    query = f"{base_title} Stagione {season_num} {' '.join(metadata_parts)}"
                    queries.append(("season-metadata", query))

            # Strategy 2: Series + Resolution + Codec (season-agnostic)
            if resolution or codec:
                metadata_parts = []
                if resolution:
                    metadata_parts.append(resolution)
                if codec:
                    metadata_parts.append(codec)

                if metadata_parts:
                    query = f"{base_title} {' '.join(metadata_parts)}"
                    queries.append(("metadata-only", query))

            # Strategy 3: Series + Resolution
            if resolution:
                query = f"{base_title} {resolution}"
                queries.append(("resolution-only", query))

            # Strategy 4: Series + Codec
            if codec:
                query = f"{base_title} {codec}"
                queries.append(("codec-only", query))

            # Strategy 5: Series + Year (if available)
            if year:
                query = f"{base_title} {year}"
                queries.append(("year-metadata", query))

            logger.debug(f"Generated {len(queries)} enhanced search queries")
            return queries

        except Exception as e:
            logger.warning(f"Error extracting enhanced search queries: {e}")
            return []

    def _extract_base_series_name(self, release_title):
        """Extract the base series name without season/episode metadata"""
        try:
            title = release_title.strip()

            # Remove common suffixes and metadata
            title = re.sub(r'\s*\[.*?\]', '', title, flags=re.IGNORECASE)  # Remove [IN CORSO], [03/10], etc.
            title = re.sub(r'\s*\([^)]*\)\s*$', '', title, flags=re.IGNORECASE)  # Remove trailing parentheses

            # Handle multi-episode ranges first
            multi_episode_pattern = r"(.*?)(?:\s+S\d+E\d+[-~]S?\d*E\d+.*|\s+S\d+E\d+E\d+.*|\s+S\d+E\d+-\d+.*|\s+S\d+E\d+~\d+.*)"
            match = re.match(multi_episode_pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).strip()

            # Look for season patterns and extract series name
            season_patterns = [
                r'\s*-\s*S\d+E\d+(?:\s*of\s*\d+)?(?:\s*-\s*\d+)?(?:\s*\[.*?\])?.*$',
                r'\s*-\s*Stagione\s*\d+(?:\s*\[.*?\])?.*$',
                r'\s*-\s*Season\s*\d+(?:\s*\[.*?\])?.*$',
                r'\s+(\d+)(?:st|nd|rd|th)\s+Season(?:\s+Episode\s+\d+)?.*$',
                r'\s+Season\s+\d+\s+Ep(?:\.|\s)?\s*\d+.*$',
                r'\s+Stagione\s+\d+\s+Ep(?:\.|\s)?\s*\d+.*$',
                r'\s+\d+x\d+(?:-\d+)?(?:\s*\[.*?\])?.*$',
                r'\s+S\d+E\d+(?:\s*of\s*\d+)?(?:\s*\[.*?\])?.*$',
                r'\s*\d+x\d+(?:\s*of\s*\d+)?(?:.*)?$',
                r'\s+Season\s*\d+(?:\s*\[.*?\])?.*$',  # Added: Season 2 without dash
                r'\s+Stagione\s*\d+(?:\s*\[.*?\])?.*$',  # Added: Stagione 2 without dash
            ]

            series_name = title
            for pattern in season_patterns:
                match = re.search(pattern, series_name, re.IGNORECASE)
                if match:
                    series_name = series_name[:match.start()].strip()
                    break

            # Clean up series name
            series_name = re.sub(r'\s+$', '', series_name)  # Trailing spaces
            series_name = re.sub(r'[-\s]+$', '', series_name)  # Trailing dashes/spaces

            # Validate series name
            if len(series_name) >= 2:
                return series_name

            return None
        except Exception as e:
            logger.warning(f"Error extracting base series name: {e}")
            return None

    def _extract_resolution(self, release_title):
        """Extract resolution from release title (e.g., 1080p, 720p, 4K)"""
        patterns = [
            r'\b(1080p|720p|2160p|4K|UHD)\b',
            r'\b(\d{3,4}p)\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, release_title, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_codec(self, release_title):
        """Extract codec from release title (e.g., H264, H265, x265)"""
        patterns = [
            r'\b(H264|H265|x264|x265|AVC|HEVC)\b',
            r'\b(XviD|DivX)\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, release_title, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_year(self, release_title):
        """Extract year from release title"""
        match = re.search(r'\b(19|20)\d{2}\b', release_title)
        if match:
            return match.group(0)
        return None

    def _extract_season_number(self, release_title):
        """Extract season number from release title"""
        patterns = [
            r'S(\d+)',
            r'Stagione\s*(\d+)',
            r'Season\s*(\d+)',
            r'(\d+)(?:st|nd|rd|th)\s+Season',
            r'(\d+)x\d+',
        ]

        for pattern in patterns:
            match = re.search(pattern, release_title, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_season_search_query(self, release_title):
        """Extract series name and season for season-level search with enhanced logic"""
        try:
            base_name = self._extract_base_series_name(release_title)
            season_num = self._extract_season_number(release_title)

            if season_num and base_name:
                return f"{base_name} - Stagione {season_num}"

            return None
        except Exception as e:
            logger.warning(f"Error extracting season search query: {e}")
            return None

    def extract_episode_info(self, magnet_element):
        """Extracts episode information from the magnet context with enhanced pattern matching"""
        try:
            # Multi-level context analysis: check multiple levels up and siblings
            context_elements = []
            current = magnet_element

            # Check parent hierarchy (up to 5 levels for better context)
            for _ in range(5):
                if current and current.parent:
                    current = current.parent
                    context_elements.append(current)
                else:
                    break

            # Check siblings of the magnet element and its parent hierarchy
            for elem in context_elements:
                if hasattr(elem, 'find_all'):
                    siblings = elem.find_all(recursive=False)
                    context_elements.extend(siblings)

            # Also check magnet element itself and immediate children
            context_elements.append(magnet_element)
            if hasattr(magnet_element, 'find_all'):
                children = magnet_element.find_all(recursive=False)
                context_elements.extend(children)

            # Remove duplicates while preserving order
            seen = set()
            unique_context = []
            for elem in context_elements:
                if elem not in seen:
                    seen.add(elem)
                    unique_context.append(elem)
            context_elements = unique_context

            # Combine all context text
            context_texts = [elem.get_text() for elem in context_elements if elem]

            # Enhanced patterns with comprehensive coverage - reordered for priority
            patterns = [
                # Combined season+episode patterns (highest priority)
                r'S(\d+)E(\d+)(?:\s*of\s*\d+)?',  # S5E04, S5E04 of 10 (adds leading zeros)
                r'(\d+)x(\d+)(?:-\d+)?',          # 5x04, 5x04-10
                r'(\d+)(?:st|nd|rd|th)\s+Season\s+Episode\s+(\d+)',  # 5th Season Episode 3
                r'Season\s+(\d+)\s+Ep(?:\.|\s)?\s*(\d+)',  # Season 2 Ep 5
                r'Stagione\s+(\d+)\s+Ep(?:\.|\s)?\s*(\d+)',  # Stagione 2 Ep 5
                # Season-level patterns (lower priority)
                r'Stagione\s*(\d+)',               # Stagione 5
                r'Season\s*(\d+)',                 # Season 5
                r'(\d+)(?:st|nd|rd|th)\s+Season',  # 5th Season
                # Single episode patterns (context-aware)
                r'(?:^|[^S]\b)Ep\.?\s*(\d+)(?:-(\d+))?',      # Ep 7, Ep 7-10
                r'(?:^|[^S]\b)Episodio\s+(\d+)(?:\s*-\s*(\d+))?',  # Episodio 7, Episodio 7-10
                # Additional variants
                r'Episode\s+(\d+)',               # Episode 7
                r'Ep\s+(\d+)',                    # Ep 7 (alternative)
            ]

            # Process patterns in order of specificity
            for text in context_texts:
                for i, pattern in enumerate(patterns):
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        groups = match.groups()
                        # Combined season+episode patterns
                        if i == 0:  # S(\d+)E(\d+) pattern
                            season = int(groups[0])
                            episode = int(groups[1])
                            return f"S{season:02d}E{episode:02d}"
                        elif i == 1:  # (\d+)x(\d+) pattern
                            season = int(groups[0])
                            episode = int(groups[1])
                            return f"S{season:02d}E{episode:02d}"
                        elif i == 2:  # (\d+)(?:st|nd|rd|th)\s+Season\s+Episode\s+(\d+)
                            season = int(groups[0])
                            episode = int(groups[1])
                            return f"S{season:02d}E{episode:02d}"
                        elif i == 3:  # Season\s+(\d+)\s+Ep(?:\.|\s)?\s*(\d+)
                            season = int(groups[0])
                            episode = int(groups[1])
                            return f"S{season:02d}E{episode:02d}"
                        elif i == 4:  # Stagione\s+(\d+)\s+Ep(?:\.|\s)?\s*(\d+)
                            season = int(groups[0])
                            episode = int(groups[1])
                            return f"S{season:02d}E{episode:02d}"
                        # Season-only patterns
                        elif i == 5:  # Stagione\s*(\d+)
                            season = int(groups[0])
                            return f"S{season:02d}E00"  # Season pack
                        elif i == 6:  # Season\s*(\d+)
                            season = int(groups[0])
                            return f"S{season:02d}E00"  # Season pack
                        elif i == 7:  # (\d+)(?:st|nd|rd|th)\s+Season
                            season = int(groups[0])
                            return f"S{season:02d}E00"  # Season pack
                        # Single episode patterns with season context
                        elif i >= 8:  # Single episode patterns
                            # Check if there's season context in the same text
                            season_context = re.search(r'S(?:tagione|eason)?\s*(\d+)', text, re.IGNORECASE)
                            if season_context:
                                season = int(season_context.group(1))
                                episode = int(groups[0])
                                return f"S{season:02d}E{episode:02d}"
                            else:
                                episode = int(groups[0])
                                return f"E{episode:02d}"
            return "Unknown"
        except Exception as e:
            logger.warning(f"Error extracting episode info: {e}")
            return "Unknown"

    def extract_episode_codes(self, magnet_title):
        # Find episode codes like S01E05 in the magnet title
        return set(re.findall(r"S\d{2}E\d{2}", magnet_title, re.IGNORECASE))

    def extract_magnets_from_thread(self, thread_url, forum_post_url=None):
        """
        Extracts all magnet links from a MIRCrew thread with enhanced backward compatibility.

        Enhanced Backward Compatibility Workflow:
        1. Feature detection: Check availability of new metadata fields (forum_post_url)
        2. Primary extraction: Attempt improved regex pattern on thread page
        3. Legacy path: If forum_post_url missing, use legacy extraction with enhanced patterns
        4. Fallback path: If forum_post_url available, fetch full post content for fallback
        5. Return results with appropriate logging

        Args:
            thread_url: URL of the forum thread
            forum_post_url: Optional URL of the specific forum post for fallback (new metadata field)

        Returns:
            List of dictionaries containing magnet information
        """
        try:
            logger.info(f"Extracting magnets from: {thread_url}")

            # Feature detection: Log availability of new metadata fields
            has_forum_post_url = forum_post_url is not None
            if has_forum_post_url:
                logger.debug("New metadata available: forum_post_url present")
            else:
                logger.info("Legacy mode: forum_post_url not available, using backward compatible extraction")

            # Primary extraction attempt with improved regex pattern
            magnets = self._extract_magnets_from_page(thread_url)

            # If primary extraction found magnets, return them
            if magnets:
                logger.info(f"Primary extraction successful: Found {len(magnets)} magnet links")
                return magnets

            # Backward compatibility paths based on available metadata
            if has_forum_post_url:
                # New path: Use forum_post_url for enhanced fallback
                logger.info("Primary extraction failed, triggering enhanced fallback mechanism")
                logger.info(f"Fetching forum post content from: {forum_post_url}")
                fallback_magnets = self._extract_magnets_from_page(forum_post_url)

                if fallback_magnets:
                    logger.info(f"Enhanced fallback extraction successful: Found {len(fallback_magnets)} magnet links")
                    return fallback_magnets
                else:
                    logger.warning("Enhanced fallback extraction also failed to find magnet links")
            else:
                # Legacy path: Enhanced extraction from thread URL only
                logger.info("Using legacy extraction path without forum_post_url")
                legacy_magnets = self._extract_magnets_legacy_mode(thread_url)

                if legacy_magnets:
                    logger.info(f"Legacy extraction successful: Found {len(legacy_magnets)} magnet links")
                    return legacy_magnets
                else:
                    logger.warning("Legacy extraction also failed to find magnet links")

            logger.info("No magnet links found after all extraction attempts")
            return []

        except Exception as e:
            logger.error(f"Error extracting magnets: {e}")
            return []

    def _extract_magnets_from_page(self, url, max_retries=3):
        """
        Helper method to extract magnets from a single page with retry logic.

        Args:
            url: URL to fetch and extract from
            max_retries: Maximum number of retry attempts

        Returns:
            List of magnet dictionaries or empty list on failure
        """
        for attempt in range(max_retries):
            try:
                # Fetch page content with timeout
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, 'html.parser')
                magnets = []

                # Primary regex pattern for magnet link extraction
                magnet_pattern = r'magnet:\?xt=urn:(?:btih|ed2k):[a-fA-F0-9]{32,64}'
                magnet_links = soup.find_all('a', href=re.compile(magnet_pattern, re.IGNORECASE))

                for link in magnet_links:
                    if not isinstance(link, Tag):
                        continue

                    magnet_url = link.attrs.get('href')
                    if not magnet_url:
                        continue

                    magnet_title = extract_magnet_title_from_url(magnet_url)
                    episode_info = self.extract_episode_info(link)

                    magnets.append({
                        'magnet': str(magnet_url).strip(),
                        'episode_info': episode_info,
                        'magnet_title': magnet_title
                    })

                logger.debug(f"Extracted {len(magnets)} magnet links from {url}")
                return magnets

            except requests.exceptions.RequestException as e:
                logger.warning(f"HTTP error on attempt {attempt+1}/{max_retries} for {url}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch {url} after {max_retries} attempts")
                    return []
                # Exponential backoff before retry
                import time
                time.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"Unexpected error extracting from {url}: {e}")
                return []

    def _extract_magnets_legacy_mode(self, thread_url):
        """
        Enhanced legacy extraction method for backward compatibility.

        This method is used when forum_post_url is not available (legacy configurations).
        It attempts multiple extraction strategies to maximize magnet discovery:

        1. Enhanced regex pattern search
        2. Alternative pattern matching for older post formats
        3. Context-aware extraction with improved element selection

        Args:
            thread_url: URL of the forum thread

        Returns:
            List of magnet dictionaries or empty list on failure
        """
        logger.debug(f"Attempting legacy extraction from: {thread_url}")

        try:
            # Fetch the thread page
            resp = self.session.get(thread_url, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Legacy extraction strategy 1: Enhanced magnet pattern search
            # Look for magnet links in various content areas for legacy compatibility
            magnet_pattern = r'magnet:\?xt=urn:(?:btih|ed2k):[a-zA-Z0-9]{8,64}(?:&.*)?'

            # Search in multiple areas of the page for legacy compatibility
            search_areas = [
                soup,  # Full page
                soup.find('div', {'class': 'content'}),  # Main content area
                soup.find('div', {'class': 'postbody'}),  # Post body
                soup.find('div', {'class': 'post-content'}),  # Alternative content area
            ]

            magnets = []

            for area in search_areas:
                if not area:
                    continue

                # Find all magnet links in this area
                magnet_links = area.find_all('a', href=re.compile(magnet_pattern))

                for link in magnet_links:
                    if not isinstance(link, Tag):
                        continue

                    magnet_url = link.attrs.get('href')
                    if not magnet_url:
                        continue

                    # Skip duplicates
                    if any(m['magnet'] == magnet_url for m in magnets):
                        continue

                    magnet_title = extract_magnet_title_from_url(magnet_url)
                    episode_info = self.extract_episode_info(link)

                    magnets.append({
                        'magnet': str(magnet_url).strip(),
                        'episode_info': episode_info,
                        'magnet_title': magnet_title
                    })

                    logger.debug(f"Found magnet in legacy extraction: {magnet_title}")

            # Legacy extraction strategy 2: Alternative text-based patterns
            # Some older posts might have magnet links in plain text format
            if not magnets:
                text_content = soup.get_text()
                # Look for magnet links that might not be in <a> tags
                alt_magnet_matches = re.findall(magnet_pattern, text_content)

                for magnet_match in alt_magnet_matches:
                    # Skip if we already have this magnet
                    if any(m['magnet'] == magnet_match for m in magnets):
                        continue

                    magnet_title = extract_magnet_title_from_url(magnet_match)
                    magnets.append({
                        'magnet': str(magnet_match).strip(),
                        'episode_info': 'Unknown',  # Can't extract from plain text
                        'magnet_title': magnet_title
                    })

                    logger.debug(f"Found magnet in legacy text extraction: {magnet_title}")

            logger.debug(f"Legacy extraction found {len(magnets)} magnet links")
            return magnets

        except Exception as e:
            logger.warning(f"Error in legacy extraction: {e}")
            return []

    def find_original_torrent(self, original_torrents, target_magnet_hash):
        """Finds the original torrent downloaded by Sonarr"""
        for torrent in original_torrents:
            if torrent.get('hash', '').lower() == target_magnet_hash:
                return torrent
        return None

    def parse_needed_episodes(self, episode_path):
        """Extracts the necessary episodes from the Sonarr path"""
        try:
            patterns = [
                r'S(\d+)E(\d+)(?:-E(\d+))?',  # S01E01 o S01E01-E03
                r'(\d+)x(\d+)(?:-(\d+))?',    # 1x01 o 1x01-03
            ]
            needed_episodes = set()
            for pattern in patterns:
                matches = re.finditer(pattern, episode_path, re.IGNORECASE)
                for match in matches:
                    season = int(match.group(1))
                    start_ep = int(match.group(2))
                    end_ep = int(match.group(3)) if match.group(3) else start_ep
                    for ep in range(start_ep, end_ep + 1):
                        needed_episodes.add(f"S{season:02d}E{ep:02d}")
            if not needed_episodes and episode_path:
                logger.warning(f"Unable to parse episodes from: {episode_path}")
            return needed_episodes
        except Exception as e:
            logger.error(f"Error parsing episodes: {e}")
            return set()