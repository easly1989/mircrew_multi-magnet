#!/usr/bin/env python3

"""
Multi-Forum Multi-Magnet Script for Sonarr
Manages the download of all episodes from any forum thread using modular architecture

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
- FORUM_TYPE: Type of forum site (default: mircrew)
- TORRENT_CLIENT: Type of torrent client (default: qbittorrent)

For MIRCrew forum (default):
- MIRCREW_BASE_URL: Base URL for MIRCrew site (default: https://mircrew-releases.org/)
- MIRCREW_USERNAME: MIRCrew username
- MIRCREW_PASSWORD: MIRCrew password

For qBittorrent (default):
- QBITTORRENT_URL: qBittorrent WebUI URL
- QBITTORRENT_USERNAME: qBittorrent username
- QBITTORRENT_PASSWORD: qBittorrent password

For other clients and forums, add their specific environment variables as needed.

ARCHITECTURE OVERVIEW
====================

This script has been refactored to support multiple forum sites and torrent clients through a modular architecture:

1. ForumExtractor Interface (forum_extractor.py)
   - Defines the abstract interface that all forum extractors must implement
   - Provides methods for login, session verification, thread search, and magnet extraction

2. Concrete Forum Implementations
   - MIRCrewExtractor (mircrew_extractor.py): Implementation for MIRCrew forum
   - Future forums can be added by implementing the ForumExtractor interface

3. Forum Extractor Factory (forum_extractor_factory.py)
   - Creates forum extractor instances based on configuration
   - Supports easy extension for new forum types

4. TorrentClient Interface (torrent_client.py)
   - Defines the abstract interface that all torrent clients must implement
   - Provides methods for login, adding magnets, getting torrents, removing torrents, and hash extraction

5. Concrete Torrent Implementations
   - QBittorrentClient (qbittorrent_client.py): Implementation for qBittorrent WebUI
   - Future clients can be added by implementing the TorrentClient interface

6. Factory Pattern (torrent_client_factory.py)
   - Creates torrent client instances based on configuration
   - Supports easy extension for new client types

7. Main Script (mircrew.py)
   - Uses the generic ForumExtractor and TorrentClient interfaces
   - No longer coupled to specific implementations
   - Can work with any forum site and torrent client that implement the interfaces

ADDING A NEW FORUM EXTRACTOR
===========================

To add support for a new forum site (e.g., AnotherForum, ExampleForum):

1. Create a new implementation file (e.g., `anotherforum_extractor.py`):
   ```python
   from forum_extractor import ForumExtractor
   from torrent_client import TorrentClient

   class AnotherForumExtractor(ForumExtractor):
       def __init__(self, torrent_client: TorrentClient):
           super().__init__(torrent_client)
           # Initialize forum-specific settings

       def login(self, retries=15, initial_wait=5) -> bool:
           # Implement forum-specific login logic
           pass

       def verify_session(self) -> bool:
           # Implement session verification
           pass

       def search_thread_by_release_title(self, release_title: str) -> Optional[str]:
           # Implement thread search logic
           pass

       def extract_magnets_from_thread(self, thread_url: str) -> List[Dict[str, Any]]:
           # Implement magnet extraction
           pass

       def extract_episode_info(self, magnet_element) -> str:
           # Implement episode info extraction
           pass

       def extract_episode_codes(self, magnet_title: str) -> set:
           # Implement episode code extraction
           pass

       def find_original_torrent(self, original_torrents, target_magnet_hash) -> Optional[Dict[str, Any]]:
           # Implement torrent finding logic
           pass

       def parse_needed_episodes(self, episode_path: str) -> set:
           # Implement episode parsing logic
           pass
   ```

2. Update the forum extractor factory (`forum_extractor_factory.py`):
   ```python
   def create_forum_extractor(forum_type: Optional[str] = None) -> ForumExtractor:
       if forum_type == 'anotherforum':
           return _create_anotherforum_extractor()
       # ... existing code
   ```

3. Add a new factory function:
   ```python
   def _create_anotherforum_extractor() -> AnotherForumExtractor:
       torrent_client = create_torrent_client()
       return AnotherForumExtractor(torrent_client)
   ```

4. Update environment variables in `.env`:
   ```
   FORUM_TYPE=anotherforum
   ANOTHERFORUM_BASE_URL=https://anotherforum.com
   ANOTHERFORUM_USERNAME=your_username
   ANOTHERFORUM_PASSWORD=your_password
   ```

5. Update the script documentation to include the new forum configuration options.

This modular architecture allows you to easily extend the script to work with any forum site by implementing the ForumExtractor interface!

TESTING
=======
The script includes dedicated test scripts for different forum implementations:

For MIRCrew Testing:
```bash
python test_mircrew.py
```

This will:
- Start the script in test mode
- Prompt for episode selection
- Use MIRCrew-specific test data
- Simulate the full workflow without making actual changes

For other forum implementations, create dedicated test scripts following the same pattern.

USAGE EXAMPLES
==============
Normal Usage (with Sonarr):
```bash
python main.py
```

Test Usage (interactive):
```bash
python test_mircrew.py
```

Configuration (.env file):
```
FORUM_TYPE=mircrew
TORRENT_CLIENT=qbittorrent
MIRCREW_BASE_URL=https://mircrew-releases.org/
MIRCREW_USERNAME=your_username
MIRCREW_PASSWORD=your_password
QBITTORRENT_URL=http://localhost:8080
QBITTORRENT_USERNAME=your_username
QBITTORRENT_PASSWORD=your_password
```
"""

import os
import dotenv
import sys
import re
import time
import logging
from torrents.torrent_client import TorrentClient
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
def main():
    """Main function of the script"""
    logger.info("=== Starting Multi-Forum Multi-Magnet Script ===")

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

    # Initialize forum extractor using factory
    from extractors.forum_extractor_factory import create_forum_extractor
    extractor = create_forum_extractor()

    # Check if already logged in
    if extractor.verify_session():
        logger.info("Forum session still valid")
        sid = True  # Already logged in
    else:
        logger.info("Session expired, attempting login...")
        sid = extractor.login()
        if not sid:
            logger.error("Unable to access forum")
            return

    if not extractor.torrent_client.login():
        logger.error("Unable to access torrent client")
        return

    thread_url = extractor.search_thread_by_release_title(release_title)
    if not thread_url:
        logger.error("I didn't find a forum thread for this release. Exiting.")
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



if __name__ == "__main__":
    main()