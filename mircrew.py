#!/usr/bin/env python3

"""
MIRCrew Multi-Magnet Script for Sonarr
Manages the download of all episodes from a MIRCrew thread

ARCHITECTURE OVERVIEW
====================

This script has been refactored to support multiple torrent clients through a modular architecture:

1. TorrentClient Interface (torrent_client.py)
   - Defines the abstract interface that all torrent clients must implement
   - Provides methods for login, adding magnets, getting torrents, removing torrents, and hash extraction

2. Concrete Implementations
   - QBittorrentClient (qbittorrent_client.py): Implementation for qBittorrent WebUI
   - Future clients can be added by implementing the TorrentClient interface

3. Factory Pattern (torrent_client_factory.py)
   - Creates torrent client instances based on configuration
   - Supports easy extension for new client types

4. Main Script (mircrew.py)
   - Uses the generic TorrentClient interface
   - No longer coupled to specific torrent client implementations
   - Can work with any torrent client that implements the interface

ADDING A NEW TORRENT CLIENT
===========================

To add support for a new torrent client (e.g., Transmission, Deluge):

1. Create a new implementation file (e.g., `transmission_client.py`):
   ```python
   from torrent_client import TorrentClient

   class TransmissionClient(TorrentClient):
       def __init__(self, url: str, username: str, password: str):
           # Initialize client
           pass

       def login(self) -> bool:
           # Implement login logic
           pass

       def add_magnet(self, magnet_url: str, category: str = None) -> bool:
           # Implement magnet addition
           pass

       def get_torrents(self) -> List[Dict[str, Any]]:
           # Return list of torrents
           pass

       def remove_torrent(self, torrent_hash: str) -> bool:
           # Implement torrent removal
           pass

       def get_torrent_hash_from_magnet(self, magnet_url: str) -> Optional[str]:
           # Extract hash from magnet
           pass
   ```

2. Update the factory (`torrent_client_factory.py`):
   ```python
   def create_torrent_client(client_type: Optional[str] = None) -> TorrentClient:
       if client_type == 'transmission':
           return _create_transmission_client()
       # ... existing code
   ```

3. Add a new factory function:
   ```python
   def _create_transmission_client() -> TransmissionClient:
       url = os.environ.get('TRANSMISSION_URL')
       username = os.environ.get('TRANSMISSION_USERNAME')
       password = os.environ.get('TRANSMISSION_PASSWORD')
       # ... validation and instantiation
   ```

4. Update environment variables in `.env`:
   ```
   TORRENT_CLIENT=transmission
   TRANSMISSION_URL=http://localhost:9091
   TRANSMISSION_USERNAME=your_username
   TRANSMISSION_PASSWORD=your_password
   ```

CONFIGURATION
=============

Required environment variables:
- MIRCREW_BASE_URL: Base URL for MIRCrew site
- MIRCREW_USERNAME: MIRCrew username
- MIRCREW_PASSWORD: MIRCrew password
- TORRENT_CLIENT: Type of torrent client (default: qbittorrent)

For qBittorrent (default):
- QBITTORRENT_URL: qBittorrent WebUI URL
- QBITTORRENT_USERNAME: qBittorrent username
- QBITTORRENT_PASSWORD: qBittorrent password

For other clients, add their specific environment variables as needed.
"""

import os
import dotenv
import sys
import re
import requests
from bs4 import BeautifulSoup, Tag
import json
import time
import logging
import pickle
from urllib.parse import urljoin, parse_qs, urlparse, unquote, quote_plus
from torrent_client import TorrentClient
dotenv.load_dotenv()

# Configuration
MIRCREW_BASE_URL = str(os.environ.get('MIRCREW_BASE_URL', 'https://mircrew-releases.org/'))
MIRCREW_USERNAME = str(os.environ.get('MIRCREW_USERNAME'))
MIRCREW_PASSWORD = str(os.environ.get('MIRCREW_PASSWORD'))

# Validate required MIRCrew environment variables
if not MIRCREW_USERNAME or not MIRCREW_PASSWORD:
    raise ValueError("Missing required MIRCrew environment variables. Please check .env file.")

# Type assertions for mypy/pylance
assert MIRCREW_USERNAME is not None
assert MIRCREW_PASSWORD is not None

# Cookie persistence
COOKIE_FILE = "mircrew_cookies.pkl"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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


class MIRCrewExtractor:
    def __init__(self, torrent_client: TorrentClient):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.torrent_client = torrent_client
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

    def login_mircrew(self, retries=15, initial_wait=5):
        """Login to MIRCrew, returns sid if ok, False if fails"""
        import random

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
            if not self.login_mircrew():
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


def main():
    """Main function of the script"""
    logger.info("=== Starting MIRCrew Multi-Magnet Script ===")

    # Read environment variables from Sonarr
    series_title = os.environ.get('sonarr_series_title', '')
    episode_file_relative_path = os.environ.get('sonarr_episodefile_relativepath', '')
    release_title = os.environ.get('sonarr_release_title', '')
    season_number = os.environ.get('sonarr_episode_seasonnumber', '')
    episode_numbers = os.environ.get('sonarr_episode_episodenumbers', '')

    logger.info(f"Series: {series_title}")
    logger.info(f"Episode path: {episode_file_relative_path}")
    logger.info(f"Season: {season_number}, Episodes: {episode_numbers}")
    logger.info(f"Release title: {release_title}")

    if not release_title:
        logger.error("Variable 'sonarr_release_title' not found, exiting.")
        sys.exit(1)

    # Initialize torrent client using factory
    from torrent_client_factory import create_torrent_client
    torrent_client = create_torrent_client()

    main_with_client(torrent_client)


def main_with_client(torrent_client):
    """Main function with a pre-initialized torrent client"""
    # Read environment variables from Sonarr
    series_title = os.environ.get('sonarr_series_title', '')
    episode_file_relative_path = os.environ.get('sonarr_episodefile_relativepath', '')
    release_title = os.environ.get('sonarr_release_title', '')
    season_number = os.environ.get('sonarr_episode_seasonnumber', '')
    episode_numbers = os.environ.get('sonarr_episode_episodenumbers', '')

    logger.info(f"Series: {series_title}")
    logger.info(f"Episode path: {episode_file_relative_path}")
    logger.info(f"Season: {season_number}, Episodes: {episode_numbers}")
    logger.info(f"Release title: {release_title}")

    if not release_title:
        logger.error("Variable 'sonarr_release_title' not found, exiting.")
        sys.exit(1)

    extractor = MIRCrewExtractor(torrent_client)

    # Check if already logged in
    if extractor.verify_session():
        logger.info("MIRCrew session still valid")
        sid = True  # Already logged in
    else:
        logger.info("Session expired, attempting login...")
        sid = extractor.login_mircrew()
        if not sid:
            logger.error("Unable to access MIRCrew")
            return

    if not extractor.torrent_client.login():
        logger.error("Unable to access torrent client")
        return
        
    thread_url = extractor.search_thread_by_release_title(release_title)
    if not thread_url:
        logger.error("I didn't find a MIRCrew thread for this release. Exiting.")
        sys.exit(0)
        
    original_torrents = extractor.torrent_client.get_torrents()
    magnets = extractor.extract_magnets_from_thread(thread_url)
    if not magnets:
        logger.warning("No magnets found in the thread")
        return

    # Try to get episodes from direct Sonarr variables first, fallback to parsing file path
    needed_episodes = set()
    process_all_episodes = False

    if season_number and episode_numbers:
        try:
            season = int(season_number)
            episodes = [int(ep.strip()) for ep in episode_numbers.split(',') if ep.strip()]
            needed_episodes = {f"S{season:02d}E{ep:02d}" for ep in episodes}
            logger.info(f"Episodes from Sonarr variables: {needed_episodes}")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing direct Sonarr variables: {e}, trying with file path")

    # Fallback to parsing file path if direct variables didn't work
    if not needed_episodes and episode_file_relative_path:
        needed_episodes = extractor.parse_needed_episodes(episode_file_relative_path)
        logger.info(f"Episodes from file path: {needed_episodes}")

    # If still no episodes found, try to extract season from release_title and process all episodes
    if not needed_episodes:
        # Try to extract season from release_title
        season_match = re.search(r'(?:stagione|season)\s*(\d+)', release_title, re.IGNORECASE)
        if season_match:
            extracted_season = int(season_match.group(1))
            logger.info(f"Season extracted from release_title: {extracted_season}")
            # When no specific episodes are provided, process all episodes of this season
            process_all_episodes = True
            logger.info("No specific episodes provided - I will process all episodes in the thread")
        else:
            logger.warning("Unable to determine season or episodes - I will process all episodes in the thread")
            process_all_episodes = True

    if process_all_episodes:
        logger.info("Mode: process all episodes")
    else:
        logger.info(f"Final needed episodes: {needed_episodes}")

    time.sleep(3)

    original_torrent_removed = False
    first_magnet_hash = None

    if magnets:
        first_magnet_hash = extractor.torrent_client.get_torrent_hash_from_magnet(magnets[0]['magnet'])
        logger.info(f"First magnet hash: {first_magnet_hash}")

    added_count = 0
    is_test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'

    for i, magnet_info in enumerate(magnets):
        magnet_url = magnet_info['magnet']
        episode_info = magnet_info['episode_info']
        magnet_title = magnet_info['magnet_title']

        episode_codes_found = extractor.extract_episode_codes(magnet_title)
        filter_by_codes = bool(needed_episodes) and not process_all_episodes

        # Management of original torrent removal if necessary
        if i == 0 and first_magnet_hash and not original_torrent_removed:
            if filter_by_codes and not episode_codes_found.intersection(needed_episodes):
                if not is_test_mode:
                    current_torrents = extractor.torrent_client.get_torrents()
                    original_torrent = extractor.find_original_torrent(current_torrents, first_magnet_hash)
                    if original_torrent:
                        if extractor.torrent_client.remove_torrent(original_torrent['hash']):
                            logger.info(f"Removed original torrent: {magnet_title}")
                            original_torrent_removed = True
                        else:
                            logger.warning("Unable to remove original torrent")
                    else:
                        logger.warning("Original torrent not found for removal")
                else:
                    logger.info(f"[TEST] I would remove original torrent: {magnet_title}")
                    original_torrent_removed = True
            else:
                logger.info(f"Keeping original torrent: {magnet_title}")
                added_count += 1
                continue

        # Skip filtering if processing all episodes
        if process_all_episodes:
            logger.debug(f"Processing all episodes - including {magnet_title}")
        elif filter_by_codes:
            if not episode_codes_found.intersection(needed_episodes):
                logger.info(f"Skipping {magnet_title} - not needed ({episode_codes_found})")
                continue

        if is_test_mode:
            logger.info(f"[TEST] I would add magnet for {magnet_title}")
            added_count += 1
        else:
            if extractor.torrent_client.add_magnet(magnet_url, category='sonarr'):
                added_count += 1
                logger.info(f"Added magnet for {magnet_title}")
                time.sleep(1)
            else:
                logger.warning(f"Unable to add magnet for {magnet_title}")

    logger.info(f"Processed {len(magnets)} magnets, added/kept {added_count}")
    logger.info("=== Script completed ===")


def test_script():
    """Function to test the script without Sonarr"""
    logger.info("=== TEST MODE ===")
    os.environ['TEST_MODE'] = 'true'
    
    # Simulate Sonarr variables for the test
    test_episodes = input("Enter required episodes (e.g.: S01E01,S01E02) or ENTER for all: ").strip()
    
    # Set simulated environment variables
    os.environ['sonarr_series_title'] = 'Only Murders in the Building'
    os.environ['sonarr_episodefile_relativepath'] = test_episodes if test_episodes else ''
    os.environ['sonarr_release_title'] = 'Only Murders in the Building - Stagione 5 (2025) [IN CORSO] [03/10] 1080p H264 ITA ENG EAC3 SUB ITA ENG - M&M.GP CreW'

    # Parse test_episodes to set direct variables if provided
    if test_episodes:
        # Try to parse S05E02 format
        match = re.search(r'S(\d+)E(\d+)', test_episodes)
        if match:
            os.environ['sonarr_episode_seasonnumber'] = match.group(1)
            os.environ['sonarr_episode_episodenumbers'] = match.group(2)
    # If no episodes specified, don't set the episode variables at all
    # This will trigger the "process all episodes" logic
    
    # Initialize torrent client for testing using factory
    from torrent_client_factory import create_torrent_client
    torrent_client = create_torrent_client()

    # Execute the script with test torrent client
    main_with_client(torrent_client)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_script()
    else:
        main()