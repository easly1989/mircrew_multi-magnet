#!/usr/bin/env python3
"""
MIRCrew Forum Extractor Implementation
Concrete implementation of ForumExtractor for MIRCrew forum.
"""

import os
import re
import requests
import time
import random
import logging
import pickle
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, parse_qs, urlparse, unquote, quote_plus
from forum_extractor import ForumExtractor
from torrent_client import TorrentClient

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
        encoded_query = quote_plus(f"\"{release_title}\"")

        params = {
            "keywords": f"{encoded_query}",  # search for the exact phrase in quotes
            "terms": "all",
            "author": "",
            "fid[]": ["28", "51", "52", "30"],  # the subforums to include in the search
            "sc": "1",
            "sf": "titleonly",  # search only in titles
            "sr": "topics",     # search among topics
            "sk": "t",          # order by title (subject)
            "sd": "d",          # descending order
            "st": "0",
            "ch": "300",
            "t": "0",
            "submit": "Cerca"
        }


        try:
            request_text = f"https://mircrew-releases.org/search.php?keywords={encoded_query}&terms=all&author=&fid%5B%5D=28&fid%5B%5D=51&fid%5B%5D=52&fid%5B%5D=30&sc=1&sf=titleonly&sr=topics&sk=t&sd=d&st=0&ch=300&t=0&submit=Cerca"

            #response = self.session.get(base_search_url, params=params)
            response = self.session.get(request_text)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"HTTP error during search on MIRCrew: {e}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the search results container specifically
        search_results_container = soup.find('ul', {'class': 'topiclist topics'})
        if not search_results_container or not isinstance(search_results_container, Tag):
            logger.warning("Search results container not found (ul.topiclist.topics)")
            return None

        logger.info("Search results container found, searching for thread...")

        # Search for viewtopic links only within the search results container
        for a in search_results_container.find_all('a', href=True):
            if not isinstance(a, Tag):
                continue
            href = a.attrs.get('href')
            if not href:
                continue

            href_str = str(href)
            logger.info(f"Found link in container: {href_str}")

            if "viewtopic.php" in href_str:
                # URL construction with proper handling of relative URLs
                if href_str.startswith('http'):
                    thread_url = href_str
                    logger.info("URL already complete (absolute)")
                else:
                    # urljoin handles "./" prefix correctly - no need to remove it
                    thread_url = urljoin(MIRCREW_BASE_URL, href_str)
                    logger.info(f"URL built from relative: '{href_str}' -> '{thread_url}'")

                logger.info(f"MIRCrew thread found: {thread_url}")
                return thread_url

        logger.warning("No MIRCrew thread found in search.")
        return None

    def extract_episode_info(self, magnet_element):
        """Extracts episode information from the magnet context"""
        try:
            parent = magnet_element.find_parent()
            if parent:
                text = parent.get_text()
                patterns = [
                    r'S(\d+)E(\d+)',
                    r'(\d+)x(\d+)',
                    r'Ep\.?\s*(\d+)',
                    r'Episodio\s+(\d+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        if len(match.groups()) == 2:
                            return f"S{match.group(1).zfill(2)}E{match.group(2).zfill(2)}"
                        else:
                            return f"E{match.group(1).zfill(2)}"
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