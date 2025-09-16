#!/usr/bin/env python3
"""
MIRCrew Test Script
Test script specifically for MIRCrew forum functionality.
"""

import os
import sys
import re
import dotenv
import logging

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main

# Load environment variables
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


def test_mircrew():
    """Test function for MIRCrew functionality"""
    logger.info("=== MIRCrew Test Mode ===")
    logger.info(f"Running in environment: {os.environ.get('HOSTNAME', 'unknown')}")

    # Set test mode
    os.environ['TEST_MODE'] = 'true'

    # Set forum type to mircrew (explicitly)
    os.environ['FORUM_TYPE'] = 'mircrew'

    # Simulate Sonarr variables for the test
    event_type = os.environ.get('sonarr_eventtype', '')
    logger.info(f"sonarr_eventtype: {event_type}")

    # Handle episode input - skip in non-interactive environments
    if event_type == 'Test':
        test_episodes = ''
        logger.info("Sonarr test mode detected - processing all episodes")
    else:
        try:
            if sys.stdin.isatty():
                test_episodes = input("Enter required episodes (e.g.: S01E01,S01E02) or ENTER for all: ").strip()
            else:
                logger.info("Running in non-interactive mode, skipping episode input")
                test_episodes = ''
        except (OSError, EOFError):
            logger.info("Input not available, skipping episode input")
            test_episodes = ''

    # Set simulated environment variables for MIRCrew
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

    logger.info(f"Test episodes: '{test_episodes}'")
    logger.info("Environment variables set for test:")
    logger.info(f"  sonarr_series_title: {os.environ.get('sonarr_series_title')}")
    logger.info(f"  sonarr_release_title: {os.environ.get('sonarr_release_title')}")
    logger.info(f"  sonarr_episode_seasonnumber: {os.environ.get('sonarr_episode_seasonnumber', 'not set')}")
    logger.info(f"  sonarr_episode_episodenumbers: {os.environ.get('sonarr_episode_episodenumbers', 'not set')}")
    logger.info(f"  TEST_MODE: {os.environ.get('TEST_MODE')}")

    # Execute the main script (it will use the configured forum extractor from .env)
    logger.info("Executing main script...")
    main()
    logger.info("Test completed successfully")


if __name__ == "__main__":
    test_mircrew()