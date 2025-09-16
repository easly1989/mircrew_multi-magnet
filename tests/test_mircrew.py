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

    # Set test mode
    os.environ['TEST_MODE'] = 'true'

    # Set forum type to mircrew (explicitly)
    os.environ['FORUM_TYPE'] = 'mircrew'

    # Simulate Sonarr variables for the test
    event_type = os.environ.get('EventType', '')
    if event_type == 'Test':
        test_episodes = ''
    else:
        test_episodes = input("Enter required episodes (e.g.: S01E01,S01E02) or ENTER for all: ").strip()

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

    # Execute the main script (it will use the configured forum extractor from .env)
    main()


if __name__ == "__main__":
    test_mircrew()