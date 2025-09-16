"""
MIRCrew Test Suite
Test suite specifically for MIRCrew forum functionality.
"""

import os
import sys
import re
import pytest
import requests
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
def test_magnet_regex_pattern(mock_torrent_client, mocker):
    """Test the improved magnet link regex pattern with real-world examples"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Mock session.get for testing extraction
    mock_get = mocker.patch.object(extractor.session, 'get')

    # Test with real magnet link format from MIRCrew site
    real_magnet_html = '''<html><body>
        <a href="magnet:?xt=urn:btih:dc898957e0a353298876efa2ba7a66fdf2b965&xl=1533538328&dn=Only.Murders.in.the.Building.S05E01.Il.dito.nella.piaga.ITA.ENG.1080p.DSNP.WEB-DL.DDP5.1.H.264-MeM.GP.mkv&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=http%3A%2F%2Ftracker.bt4g.com%3A2095%2Fannounce">Download S05E01</a>
    </body></html>'''

    mock_response = mocker.MagicMock()
    mock_response.text = real_magnet_html
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    magnets = extractor._extract_magnets_from_page("http://example.com/test")
    assert len(magnets) == 1
    assert magnets[0]['magnet'].startswith("magnet:?xt=urn:btih:dc898957e0a353298876efa2ba7a66fdf2b965")
    assert "Only.Murders.in.the.Building.S05E01" in magnets[0]['magnet_title']

    # Test with various hash lengths and formats
    test_cases = [
        # 40-character SHA-1 hash
        ("magnet:?xt=urn:btih:1234567890123456789012345678901234567890&dn=SHA1_Test", "SHA1_Test"),
        # 32-character hash
        ("magnet:?xt=urn:btih:abcdef12345678901234567890123456&dn=Short_Test", "Short_Test"),
        # 64-character hash (SHA-256)
        ("magnet:?xt=urn:btih:fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321&dn=SHA256_Test", "SHA256_Test"),
        # eD2k hash
        ("magnet:?xt=urn:ed2k:1234567890123456789012345678901234567890&dn=ED2K_Test", "ED2K_Test"),
        # With multiple trackers and metadata
        ("magnet:?xt=urn:btih:aaaaa111112222333334444555556666777778888&dn=Test.File.mkv&tr=udp://tracker1&tr=http://tracker2", "Multi_Tracker_Test"),
    ]

    for magnet_url, expected_title_base in test_cases:
        html = f'<a href="{magnet_url}">{expected_title_base}</a>'
        mock_response.text = f'<html><body>{html}</body></html>'

        magnets = extractor._extract_magnets_from_page("http://example.com/test")
        assert len(magnets) == 1, f"Failed to extract magnet: {magnet_url}"
        # Note: BeautifulSoup might unescape the HTML entities, so check the unescaped version
        expected_unescaped = magnet_url.replace('&', '&')
        assert magnets[0]['magnet'] == expected_unescaped, f"Magnet URL mismatch for: {magnet_url}"

    # Test invalid magnet links (should not be extracted)
    invalid_cases = [
        "magnet:?xt=urn:btih:short",  # Too short hash
        "magnet:?xt=urn:invalid:1234567890123456789012345678901234567890",  # Wrong URN type
        "magnet:?dn=Test&tr=tracker",  # Missing xt parameter
        "magnet:?xt=urn:btih:gggggggggggggggggggggggggggggggggggggggg",  # Non-hex (but valid length)
    ]

    for invalid_magnet in invalid_cases:
        html = f'<a href="{invalid_magnet}">Invalid Magnet</a>'
        mock_response.text = f'<html><body>{html}</body></html>'

        magnets = extractor._extract_magnets_from_page("http://example.com/test")
        assert len(magnets) == 0, f"Should not have extracted invalid magnet: {invalid_magnet}"


def test_fallback_mechanism(mock_torrent_client, mocker):
    """Test the fallback mechanism in magnet extraction"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Mock the session.get method
    mock_get = mocker.patch.object(extractor.session, 'get')

    # Test case 1: Primary extraction succeeds
    primary_html = '<html><body><a href="magnet:?xt=urn:btih:1234567890123456789012345678901234567890&dn=Primary.Test">Primary Magnet</a></body></html>'
    mock_response = mocker.MagicMock()
    mock_response.text = primary_html
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", None)
    assert len(magnets) == 1
    assert magnets[0]['magnet'] == "magnet:?xt=urn:btih:1234567890123456789012345678901234567890&dn=Primary.Test"

    # Test case 2: Primary fails, fallback succeeds with real magnet format
    def side_effect(url, timeout=None):
        mock_resp = mocker.MagicMock()
        if "thread" in url:
            # Primary URL returns no magnets
            mock_resp.text = '<html><body><p>No magnets here</p></body></html>'
        else:
            # Fallback URL returns real format magnet
            mock_resp.text = '<html><body><a href="magnet:?xt=urn:btih:dc898957e0a353298876efa2ba7a66fdf2b965&dn=Only.Murders.in.the.Building.S05E01">Fallback Magnet</a></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get.side_effect = side_effect
    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert len(magnets) == 1
    assert magnets[0]['magnet'].startswith("magnet:?xt=urn:btih:dc898957e0a353298876efa2ba7a66fdf2b965")

    # Test case 3: Both primary and fallback fail
    mock_get.side_effect = lambda url, timeout=None: mocker.MagicMock(
        text='<html><body><p>No magnets</p></body></html>',
        raise_for_status=lambda: None
    )
    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert magnets == []

    # Test case 4: HTTP error on primary, fallback succeeds
    def error_side_effect(url, timeout=None):
        if "thread" in url:
            raise requests.exceptions.RequestException("Primary failed")
        mock_resp = mocker.MagicMock()
        mock_resp.text = '<html><body><a href="magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcdef&dn=Error.Fallback">Error Fallback</a></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get.side_effect = error_side_effect
    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert len(magnets) == 1
    assert "abcdef123456789012345678901234567890abcdef" in magnets[0]['magnet']

    # Test case 5: Timeout scenario
    def timeout_side_effect(url, timeout=None):
        if "thread" in url:
            raise requests.exceptions.Timeout("Timeout on primary")
        mock_resp = mocker.MagicMock()
        mock_resp.text = '<html><body><a href="magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcdef&dn=Timeout.Fallback">Timeout Fallback</a></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get.side_effect = timeout_side_effect
    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert len(magnets) == 1
    assert "abcdef123456789012345678901234567890abcdef" in magnets[0]['magnet']


def test_metadata_handling(mock_torrent_client, mocker):
    """Test metadata handling, specifically forum_post_url usage"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Mock the session.get method
    mock_get = mocker.patch.object(extractor.session, 'get')

    # Test case 1: forum_post_url provided and used successfully
    def success_side_effect(url, timeout=None):
        mock_resp = mocker.MagicMock()
        if "thread" in url:
            # Primary fails
            mock_resp.text = '<html><body><p>No magnets in thread</p></body></html>'
        else:
            # Fallback succeeds
            mock_resp.text = '<html><body><a href="magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcd&dn=Metadata.Test">Metadata Magnet</a></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get.side_effect = success_side_effect
    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert len(magnets) == 1
    assert magnets[0]['magnet'] == "magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcd&dn=Metadata.Test"

    # Test case 2: forum_post_url is None, no fallback attempted
    mock_get.side_effect = lambda url, timeout=None: mocker.MagicMock(
        text='<html><body><p>No magnets here</p></body></html>',
        raise_for_status=lambda: None
    )
    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", None)
    assert magnets == []

    # Verify that when forum_post_url is None, only primary URL is called (with retries)
    assert mock_get.call_count == 4  # Primary extraction with retries + legacy extraction

    # Test case 3: forum_post_url provided but fallback also fails
    def fail_side_effect(url, timeout=None):
        mock_resp = mocker.MagicMock()
        mock_resp.text = '<html><body><p>No magnets available</p></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get.side_effect = fail_side_effect
    magnets = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert magnets == []


def test_extraction_retry_logic(mock_torrent_client, mocker):
    """Test retry logic in magnet extraction"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Mock time.sleep to speed up tests
    mock_sleep = mocker.patch('time.sleep')

    # Test successful extraction on first attempt
    mock_response = mocker.MagicMock()
    mock_response.text = '<html><body><a href="magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcdef&dn=Retry.Test">Retry Test</a></body></html>'
    mock_response.raise_for_status.return_value = None
    mock_get = mocker.patch.object(extractor.session, 'get', return_value=mock_response)

    magnets = extractor._extract_magnets_from_page("http://example.com/page")
    assert len(magnets) == 1
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()

    # Test retry on HTTP error
    call_count = 0
    def error_then_success(url, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise requests.exceptions.RequestException("Temporary error")
        mock_resp = mocker.MagicMock()
        mock_resp.text = '<html><body><a href="magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcdef&dn=Retry.After.Error">Retry After Error</a></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get.reset_mock()  # Reset the mock call count
    mock_get.side_effect = error_then_success
    magnets = extractor._extract_magnets_from_page("http://example.com/page")
    assert len(magnets) == 1
    assert call_count == 3  # Should have retried twice before succeeding
    assert mock_get.call_count == 3  # Should have called get 3 times
    assert mock_sleep.call_count == 2  # Should have slept twice

    # Test max retries exceeded
    mock_get.reset_mock()  # Reset the mock call count
    mock_sleep.reset_mock()  # Reset sleep call count
    mock_get.side_effect = requests.exceptions.RequestException("Persistent error")
    magnets = extractor._extract_magnets_from_page("http://example.com/page")
    assert magnets == []
    assert mock_get.call_count == 3  # Max retries (default 3)

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


def test_backward_compatibility_feature_detection(mock_torrent_client, mocker):
    """Test feature detection for backward compatibility"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Mock _extract_magnets_from_page to return empty list (primary extraction fails)
    mock_extract = mocker.patch.object(extractor, '_extract_magnets_from_page', return_value=[])

    # Mock session.get to avoid actual HTTP calls
    mock_get = mocker.patch.object(extractor.session, 'get')
    mock_resp = mocker.MagicMock()
    mock_resp.text = '<html><body><p>No magnets</p></body></html>'
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    # Test case 1: New metadata available (forum_post_url present)
    mock_info = mocker.patch('extractors.mircrew_extractor.logger.info')
    extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    # Should log that new metadata is available
    mock_info.assert_any_call("Extracting magnets from: http://example.com/thread")

    # Test case 2: Legacy mode (forum_post_url missing)
    mock_info = mocker.patch('extractors.mircrew_extractor.logger.info')
    extractor.extract_magnets_from_thread("http://example.com/thread", None)
    # Should log legacy mode
    mock_info.assert_any_call("Legacy mode: forum_post_url not available, using backward compatible extraction")


def test_legacy_extraction_path(mock_torrent_client, mocker):
    """Test the legacy extraction path when forum_post_url is missing"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Mock primary extraction to fail
    mock_get = mocker.patch.object(extractor.session, 'get')
    mock_response = mocker.MagicMock()
    mock_response.text = '<html><body><p>No magnets found in primary</p></body></html>'
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # Mock _extract_magnets_legacy_mode to succeed
    legacy_magnets = [{'magnet': 'magnet:?xt=urn:btih:legacy123', 'episode_info': 'S01E01', 'magnet_title': 'Legacy Test'}]
    mock_legacy = mocker.patch.object(extractor, '_extract_magnets_legacy_mode', return_value=legacy_magnets)
    mock_info = mocker.patch('extractors.mircrew_extractor.logger.info')
    result = extractor.extract_magnets_from_thread("http://example.com/thread", None)

    # Should call legacy extraction
    mock_legacy.assert_called_once_with("http://example.com/thread")

    # Should return legacy results
    assert result == legacy_magnets

    # Should log legacy path usage
    mock_info.assert_any_call("Using legacy extraction path without forum_post_url")


def test_enhanced_fallback_vs_legacy_mode(mock_torrent_client, mocker):
    """Test the difference between enhanced fallback and legacy mode"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Mock session.get for both thread and post URLs
    def mock_get_side_effect(url, timeout=None):
        mock_resp = mocker.MagicMock()
        if "thread" in url:
            mock_resp.text = '<html><body><p>No magnets in thread</p></body></html>'
        else:  # post URL
            mock_resp.text = '<html><body><a href="magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcdef&dn=Fallback.Test">Fallback Magnet</a></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get = mocker.patch.object(extractor.session, 'get', side_effect=mock_get_side_effect)

    # Test case 1: Enhanced fallback with forum_post_url
    # Don't mock _extract_magnets_from_page so it uses the real session.get side_effect
    result = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert len(result) == 1
    assert "abcdef123456789012345678901234567890abcdef" in result[0]['magnet']

    # Test case 2: Legacy mode without forum_post_url
    legacy_magnets = [{'magnet': 'magnet:?xt=urn:btih:legacy456', 'episode_info': 'S01E02', 'magnet_title': 'Legacy Magnet'}]
    mock_extract = mocker.patch.object(extractor, '_extract_magnets_from_page', return_value=[])
    mock_legacy = mocker.patch.object(extractor, '_extract_magnets_legacy_mode', return_value=legacy_magnets)

    result = extractor.extract_magnets_from_thread("http://example.com/thread", None)
    assert result == legacy_magnets
    mock_legacy.assert_called_once_with("http://example.com/thread")


def test_legacy_extraction_magnet_discovery(mock_torrent_client, mocker):
    """Test the legacy extraction method's magnet discovery capabilities"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Test HTML with magnet links in different content areas
    test_html = '''
    <html>
        <body>
            <div class="content">
                <div class="postbody">
                    <a href="magnet:?xt=urn:btih:postbody123&dn=PostBody.Magnet">Post Body Magnet</a>
                </div>
                <div class="post-content">
                    <a href="magnet:?xt=urn:btih:postcontent456&dn=PostContent.Magnet">Post Content Magnet</a>
                </div>
            </div>
            <a href="magnet:?xt=urn:btih:general789&dn=General.Magnet">General Magnet</a>
        </body>
    </html>
    '''

    mock_response = mocker.MagicMock()
    mock_response.text = test_html
    mock_response.raise_for_status.return_value = None

    mock_get = mocker.patch.object(extractor.session, 'get', return_value=mock_response)

    result = extractor._extract_magnets_legacy_mode("http://example.com/thread")

    # Should find all three magnet links
    assert len(result) == 3

    # Check that different magnet URLs are found
    magnet_urls = [m['magnet'] for m in result]
    assert any("postbody123" in url for url in magnet_urls)
    assert any("postcontent456" in url for url in magnet_urls)
    assert any("general789" in url for url in magnet_urls)


def test_legacy_extraction_text_pattern_fallback(mock_torrent_client, mocker):
    """Test legacy extraction's text-based pattern fallback"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # HTML with magnet links in plain text (not in <a> tags)
    test_html = '''
    <html>
        <body>
            <div class="content">
                <p>Here is a magnet link: magnet:?xt=urn:btih:textmagnet123&dn=Text.Magnet</p>
                <p>Another one: magnet:?xt=urn:btih:another456&dn=Another.Magnet</p>
            </div>
        </body>
    </html>
    '''

    mock_response = mocker.MagicMock()
    mock_response.text = test_html
    mock_response.raise_for_status.return_value = None

    mock_get = mocker.patch.object(extractor.session, 'get', return_value=mock_response)

    result = extractor._extract_magnets_legacy_mode("http://example.com/thread")

    # Should find magnet links in plain text
    assert len(result) == 2
    magnet_urls = [m['magnet'] for m in result]
    assert any("textmagnet123" in url for url in magnet_urls)
    assert any("another456" in url for url in magnet_urls)


def test_backward_compatibility_error_handling(mock_torrent_client, mocker):
    """Test error handling in backward compatibility scenarios"""
    extractor = MIRCrewExtractor(mock_torrent_client)

    # Test case 1: Primary extraction fails with HTTP error, forum_post_url available
    def error_side_effect(url, timeout=None):
        if "thread" in url:
            raise requests.exceptions.RequestException("Primary failed")
        # Fallback succeeds
        mock_resp = mocker.MagicMock()
        mock_resp.text = '<html><body><a href="magnet:?xt=urn:btih:abcdef123456789012345678901234567890abcdef&dn=Fallback.Magnet">Fallback</a></body></html>'
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_get = mocker.patch.object(extractor.session, 'get', side_effect=error_side_effect)

    result = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    # The _extract_magnets_from_page method has retry logic, so it will catch the exception
    # and the fallback should work
    assert len(result) == 1
    assert "abcdef123456789012345678901234567890abcdef" in result[0]['magnet']

    # Test case 2: Both primary and fallback fail
    mock_get.side_effect = requests.exceptions.RequestException("Both failed")

    result = extractor.extract_magnets_from_thread("http://example.com/thread", "http://example.com/post")
    assert result == []