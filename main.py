#!/usr/bin/env python3

"""
Multi-Forum Multi-Magnet Script for Sonarr
Manages the download of all episodes from any forum thread using modular architecture

"""

import os
import dotenv
import sys
import re
import time
import logging
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
    series_title = os.environ.get('SONARR_SERIES_TITLE', '')
    episode_file_relative_path = os.environ.get('SONARR_EPISODEFILE_RELATIVEPATH', '')
    release_title = os.environ.get('SONARR_RELEASE_TITLE', '')
    season_number = os.environ.get('SONARR_EPISODE_SEASONNUMBER', '')
    episode_numbers = os.environ.get('SONARR_EPISODE_EPISODENUMBERS', '')

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