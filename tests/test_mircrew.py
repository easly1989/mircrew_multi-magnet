"""
MIRCrew Test Suite
Test suite specifically for MIRCrew forum functionality.
"""

import os
import sys
import re
import pytest
from unittest.mock import MagicMock

# Add the parent directory to the path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main
from extractors.mircrew_extractor import MIRCrewExtractor
from torrents.torrent_client import TorrentClient


def test_mircrew():
    """Test function for MIRCrew functionality"""
    # Set test mode
    os.environ['TEST_MODE'] = 'true'

    # Set forum type to mircrew (explicitly)
    os.environ['FORUM_TYPE'] = 'mircrew'

    # Simulate Sonarr variables for the test
    event_type = os.environ.get('sonarr_eventtype', '')

    # Handle episode input - skip in non-interactive environments
    if event_type == 'Test':
        test_episodes = ''
    else:
        try:
            if sys.stdin.isatty():
                test_episodes = input("Enter required episodes (e.g.: S01E01,S01E02) or ENTER for all: ").strip()
            else:
                test_episodes = ''
        except (OSError, EOFError):
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

    # Execute the main script (it will use the configured forum extractor from .env)
    # Note: This is an integration test - in a real pytest setup you might want to mock this
    try:
        main()
        assert True  # If we get here without exception, test passes
    except Exception as e:
        pytest.fail(f"Main execution failed with error: {e}")


@pytest.fixture
def mock_torrent_client():
    """Mock torrent client for testing"""
    class MockTorrentClient(TorrentClient):
        def login(self) -> bool:
            return True

        def add_magnet(self, magnet_url: str, category=None) -> bool:
            return True

        def get_torrents(self):
            return []

        def remove_torrent(self, torrent_hash: str) -> bool:
            return True

        def get_torrent_hash_from_magnet(self, magnet_url: str):
            return "mock_hash"
    return MockTorrentClient()

def test_episode_pattern_matching(mock_torrent_client):
    """Test the enhanced episode pattern matching with comprehensive test cases"""
    from bs4 import BeautifulSoup

    extractor = MIRCrewExtractor(mock_torrent_client)

    # Comprehensive test cases covering all pattern types
    test_cases = [
        # 1. Standard SxEyy with leading zero conversion
        ("Only Murders in the Building - S5E04 of 10 (2025) 1080p H264 ITA ENG", "S05E04"),
        # 2. Season-level patterns (Stagione)
        ("Test Show - Stagione 3 [IN CORSO]", "S03E00"),
        # 3. Season-level patterns (Season)
        ("Another Show Season 2 (2024)", "S02E00"),
        # 4. Classic x format
        ("Classic Format 3x12", "S03E12"),
        # 5. Single episode patterns (Ep)
        ("Single Episode Show - Ep 7", "E07"),
        # 6. Single episode patterns (Episodio)
        ("Italian Show - Episodio 15", "E15"),
        # 7. Complex format with metadata
        ("Complex Show S4E08 of 12 (2024) 720p", "S04E08"),
        # 8. Ordinal season format
        ("Ordinal Test - 5th Season Episode 3", "S05E03"),
        # 9. Mixed context (season in text with episode)
        ("Mixed Context Show Season 2 Ep 5", "S02E05"),
        # 10. Italian season + episode pattern
        ("Italian Mixed - Stagione 4 Ep 8", "S04E08"),
        # 11. Ordinal season with episode (alternative format)
        ("3rd Season Episode 12", "S03E12"),
        # 12. Season episode with metadata cleanup
        ("Series Name S2E15 of 20 [Multi-Subs] (2023)", "S02E15")
    ]

    for i, (test_input, expected) in enumerate(test_cases, 1):
        # Create a mock element for testing
        soup = BeautifulSoup(f'<div>{test_input}</div>', 'html.parser')
        mock_element = soup.find('div')

        result = extractor.extract_episode_info(mock_element)
        assert result == expected, f"Test {i}: '{test_input}' -> got '{result}', expected '{expected}'"

def test_episode_pattern_multilevel_context(mock_torrent_client):
    """Test multi-level context analysis for episode extraction"""
    from bs4 import BeautifulSoup

    extractor = MIRCrewExtractor(mock_torrent_client)

    complex_html = '''
    <div class="post-content">
        <h3>Only Murders in the Building - S5E04 of 10</h3>
        <p>Season 5 Episode 4 discussion</p>
        <a href="magnet:?xt=urn:btih:...">Download S5E04</a>
    </div>
    '''
    soup = BeautifulSoup(complex_html, 'html.parser')
    magnet_link = soup.find('a')
    result = extractor.extract_episode_info(magnet_link)
    assert result == "S05E04", f"Multi-level context analysis failed: got '{result}', expected 'S05E04'"

def test_season_search_extraction(mock_torrent_client):
    """Test the enhanced season search query extraction with comprehensive cases"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Comprehensive test cases for season extraction
    test_cases = [
        # Original example from architect
        ("Only Murders in the Building - S5E04 of 10 (2025) 1080p H264 ITA ENG EAC3 SUB ITA ENG - M&M.GP CreW", "Only Murders in the Building - Stagione 5"),
        # Stagione format
        ("Test Show - Stagione 3 [IN CORSO]", "Test Show - Stagione 3"),
        # Season format
        ("Another Show Season 2 (2024)", "Another Show - Stagione 2"),
        # Ordinal format
        ("Series Name 5th Season (2023)", "Series Name - Stagione 5"),
        # Complex metadata removal
        ("Complex Show S4E08 of 12 (2024) 720p WEB-DL [Multi-Subs]", "Complex Show - Stagione 4"),
        # No season info
        ("No Season Info Here", None),
        # Edge case with multiple patterns
        ("Edge Case Show S2E5 and Stagione 2", "Edge Case Show - Stagione 2"),
        # Minimal series name
        ("Short - S1E01", "Short - Stagione 1"),
        # New patterns to test
        ("Series with Season X Ep Y - Season 3 Ep 4 (2024)", "Series with Season X Ep Y - Stagione 3"),
        ("Ordinal with Episode - 5th Season Episode 3 (2023)", "Ordinal with Episode - Stagione 5"),
        ("Italian Season Ep - Stagione 2 Ep 5 [IN CORSO]", "Italian Season Ep - Stagione 2"),
        ("Complex x Format 4x08 of 12 (2024) 720p", "Complex x Format - Stagione 4"),
        # Edge cases
        ("Series Name S3E12-S3E15", "Series Name S3E12 - Stagione 3"),
        ("Show with 5th Season Episode 8", "Show with - Stagione 5"),
    ]

    for i, (test_input, expected) in enumerate(test_cases, 1):
        result = extractor._extract_season_search_query(test_input)
        assert result == expected, f"Test {i}: '{test_input}' -> got '{result}', expected '{expected}'"