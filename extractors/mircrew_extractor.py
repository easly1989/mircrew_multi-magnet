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
        self.load_cookies()

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

    def search_thread_by_release_title(self, release_title):
        """Search thread by release title using the existing session"""
        if not self.verify_session():
            logger.warning("Session expired, attempting re-login...")
            if not self.login():
                logger.error("Re-login failed")
                return None
            logger.info("Re-login successful, continuing search...")

        base_search_url = urljoin(MIRCREW_BASE_URL, "search.php")

        # First attempt: exact match with full title
        logger.info(f"Searching for exact match: {release_title}")
        encoded_query = quote_plus(f"\"{release_title}\"")
        thread_url = self._perform_search(encoded_query)

        if thread_url:
            logger.info("Found thread with exact match")
            return thread_url

        # Second attempt: season-level fallback
        logger.info("Exact match failed, trying season-level search...")
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

    def _perform_search(self, encoded_query):
        """Perform the actual search with given query"""
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

        for a in search_results_container.find_all('a', href=True):
            if not isinstance(a, Tag):
                continue
            href = a.attrs.get('href')
            if not href:
                continue

            href_str = str(href)
            logger.info(f"Found link in container: {href_str}")

            if "viewtopic.php" in href_str:
                if href_str.startswith('http'):
                    thread_url = href_str
                    logger.info("URL already complete (absolute)")
                else:
                    thread_url = urljoin(MIRCREW_BASE_URL, href_str)
                    logger.info(f"URL built from relative: '{href_str}' -> '{thread_url}'")

                logger.info(f"MIRCrew thread found: {thread_url}")
                return thread_url

        logger.warning("No MIRCrew thread found in search.")
        return None

    def _extract_season_search_query(self, release_title):
        """Extract series name and season for season-level search with enhanced logic"""
        try:
            title = release_title.strip()

            # Enhanced series name extraction
            # Remove common suffixes and metadata first
            title = re.sub(r'\s*\[.*?\]', '', title, flags=re.IGNORECASE)  # Remove [IN CORSO], [03/10], etc.
            title = re.sub(r'\s*\(.*?\)\s*$', '', title, flags=re.IGNORECASE)  # Remove trailing parentheses

            # Look for season patterns and extract series name - more comprehensive
            season_patterns = [
                r'\s*-\s*S\d+E\d+(?:\s*of\s*\d+)?(?:\s*-\s*\d+)?(?:\s*\[.*?\])?.*$',      # " - S5E04 of 10 [IN CORSO]"
                r'\s*-\s*Stagione\s*\d+(?:\s*\[.*?\])?.*$', # " - Stagione 5 [IN CORSO]"
                r'\s*-\s*Season\s*\d+(?:\s*\[.*?\])?.*$',   # " - Season 5 [IN CORSO]"
                r'\s+(\d+)(?:st|nd|rd|th)\s+Season(?:\s+Episode\s+\d+)?.*$',  # " 5th Season" or " 5th Season Episode 3"
                r'\s+Season\s+\d+\s+Ep(?:\.|\s)?\s*\d+.*$',  # " Season 2 Ep 5"
                r'\s+Stagione\s+\d+\s+Ep(?:\.|\s)?\s*\d+.*$',  # " Stagione 2 Ep 5"
                r'\s+\d+x\d+(?:-\d+)?(?:\s*\[.*?\])?.*$',  # " 5x04 [IN CORSO]"
                # Additional patterns for edge cases
                r'\s+Season\s+\d+(?:\s*\(.*?\))?(?:\s*\[.*?\])?.*$',   # " Season 2 (2024) [IN CORSO]"
                r'\s*S\d+E\d+(?:\s*of\s*\d+)?(?:\s*\[.*?\])?.*$',      # " S4E08 of 12 [Multi-Subs]"
                r'\s*S\d+E\d+(?:-\S+)*$',            # " S3E12" or " S3E12-S3E15" (allow multiple non-space sequences)
                r'\s*\d+x\d+(?:\s*of\s*\d+)?(?:.*)?$',  # "4x08 of 12 (2024) 720p"
            ]

            series_name = title
            for pattern in season_patterns:
                match = re.search(pattern, series_name, re.IGNORECASE)
                if match:
                    series_name = series_name[:match.start()].strip()
                    break

            # Clean up series name - remove common artifacts
            series_name = re.sub(r'\s+$', '', series_name)  # Trailing spaces
            series_name = re.sub(r'[-\s]+$', '', series_name)  # Trailing dashes/spaces

            # If no season pattern found, try to extract from common formats
            if series_name == title:
                # Try patterns like "Series Name (2025)" or "Series Name [IN CORSO]"
                alt_match = re.search(r'^([^-\(\[\s]+(?:\s+[^-\(\[\s]+)*)', title)
                if alt_match:
                    series_name = alt_match.group(1).strip()

            # Enhanced season number extraction
            season_patterns = [
                r'S(\d+)',           # S5E04
                r'Stagione\s*(\d+)', # Stagione 5
                r'Season\s*(\d+)',   # Season 5
                r'(\d+)(?:st|nd|rd|th)\s+Season',  # 5th Season
                r'(\d+)(?:st|nd|rd|th)\s+S',  # 5th S (season abbreviation)
                r'(\d+)x\d+',        # 4x08 format - extract season number
            ]

            season_num = None
            for pattern in season_patterns:
                match = re.search(pattern, release_title, re.IGNORECASE)
                if match:
                    season_num = match.group(1)
                    break

            if season_num and series_name:
                # Validate series name has minimum length
                if len(series_name) >= 2:
                    return f"{series_name} - Stagione {season_num}"

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

    def extract_magnets_from_thread(self, thread_url):
        """Extracts all magnet links from a MIRCrew thread"""
        try:
            logger.info(f"Extracting magnets from: {thread_url}")
            resp = self.session.get(thread_url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            magnets = []
            magnet_links = soup.find_all('a', href=re.compile(r'magnet:\?xt='))
            for link in magnet_links:
                magnet_url = link.attrs.get('href') if isinstance(link, Tag) else None
                if not magnet_url:
                    continue
                if magnet_url:
                    magnet_title = extract_magnet_title_from_url(magnet_url)
                    episode_info = self.extract_episode_info(link)
                    magnets.append({
                        'magnet': str(magnet_url).strip(),
                        'episode_info': episode_info,
                        'magnet_title': magnet_title
                    })
            logger.info(f"Found {len(magnets)} magnet links")
            return magnets
        except Exception as e:
            logger.error(f"Error extracting magnets: {e}")
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