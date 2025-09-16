"""
Tests for Sonarr API client
"""

import pytest
from unittest.mock import MagicMock, patch
from api.sonarr_api import SonarrAPI


class TestSonarrAPI:
    """Test suite for SonarrAPI class"""

    def test_init_with_env_vars(self):
        """Test initialization with environment variables"""
        with patch.dict('os.environ', {
            'sonarr_applicationurl': 'http://localhost:8989',
            'sonarr_apikey': 'test-key'
        }):
            api = SonarrAPI()
            assert api.base_url == 'http://localhost:8989'
            assert api.api_key == 'test-key'

    def test_init_with_params(self):
        """Test initialization with explicit parameters"""
        api = SonarrAPI(base_url='http://test.com', api_key='test-key')
        assert api.base_url == 'http://test.com'
        assert api.api_key == 'test-key'

    def test_init_rstrip_url(self):
        """Test that trailing slash is removed from base URL"""
        api = SonarrAPI(base_url='http://test.com/')
        assert api.base_url == 'http://test.com'

    @patch('requests.Session.get')
    def test_get_series_episodes_success(self, mock_get):
        """Test successful retrieval of series episodes"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {'id': 1, 'seasonNumber': 1, 'episodeNumber': 1, 'hasFile': True}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        api = SonarrAPI(base_url='http://localhost:8989', api_key='test-key')
        result = api.get_series_episodes(123)

        assert len(result) == 1
        assert result[0]['id'] == 1
        mock_get.assert_called_once_with('http://localhost:8989/api/v3/episode', params={'seriesId': 123})

    @patch('requests.Session.get')
    def test_get_series_episodes_failure(self, mock_get):
        """Test handling of API failure when getting episodes"""
        mock_get.side_effect = Exception("API Error")

        api = SonarrAPI()
        result = api.get_series_episodes(123)

        assert result == []

    @patch('requests.Session.get')
    def test_get_series_by_title_found(self, mock_get):
        """Test finding series by exact title match"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {'id': 1, 'title': 'Test Series'},
            {'id': 2, 'title': 'Another Series'}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        api = SonarrAPI()
        result = api.get_series_by_title('Test Series')

        assert result is not None
        assert result['id'] == 1
        assert result['title'] == 'Test Series'

    @patch('requests.Session.get')
    def test_get_series_by_title_case_insensitive(self, mock_get):
        """Test case-insensitive title matching"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {'id': 1, 'title': 'Test Series'}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        api = SonarrAPI()
        result = api.get_series_by_title('test series')

        assert result is not None
        assert result['id'] == 1

    @patch('requests.Session.get')
    def test_get_series_by_title_not_found(self, mock_get):
        """Test handling when series is not found"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {'id': 1, 'title': 'Test Series'}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        api = SonarrAPI()
        result = api.get_series_by_title('Nonexistent Series')

        assert result is None

    @patch('requests.Session.get')
    def test_get_series_by_title_api_failure(self, mock_get):
        """Test handling of API failure when getting series"""
        mock_get.side_effect = Exception("API Error")

        api = SonarrAPI()
        result = api.get_series_by_title('Test Series')

        assert result is None

    @patch('api.sonarr_api.SonarrAPI.get_series_by_title')
    @patch('api.sonarr_api.SonarrAPI.get_series_episodes')
    def test_get_existing_episodes_success(self, mock_get_episodes, mock_get_series):
        """Test successful retrieval of existing episodes"""
        mock_get_series.return_value = {'id': 1, 'title': 'Test Series'}

        mock_get_episodes.return_value = [
            {'seasonNumber': 1, 'episodeNumber': 1, 'hasFile': True},
            {'seasonNumber': 1, 'episodeNumber': 2, 'hasFile': True},
            {'seasonNumber': 2, 'episodeNumber': 1, 'hasFile': False},
        ]

        api = SonarrAPI()
        result = api.get_existing_episodes('Test Series')

        expected = {'S01E01', 'S01E02'}
        assert result == expected

    @patch('api.sonarr_api.SonarrAPI.get_series_by_title')
    def test_get_existing_episodes_series_not_found(self, mock_get_series):
        """Test handling when series is not found"""
        mock_get_series.return_value = None

        api = SonarrAPI()
        result = api.get_existing_episodes('Nonexistent Series')

        assert result == set()

    @patch('api.sonarr_api.SonarrAPI.get_series_by_title')
    def test_get_existing_episodes_api_failure(self, mock_get_series):
        """Test handling of API failure during episode retrieval"""
        mock_get_series.side_effect = Exception("API Error")

        api = SonarrAPI()
        result = api.get_existing_episodes('Test Series')

        assert result == set()

    def test_get_existing_episodes_no_api_config(self):
        """Test that empty set is returned when API is not configured"""
        api = SonarrAPI(base_url='', api_key='')
        result = api.get_existing_episodes('Test Series')

        assert result == set()

    @patch('api.sonarr_api.SonarrAPI.get_series_by_title')
    @patch('api.sonarr_api.SonarrAPI.get_series_episodes')
    def test_get_existing_episodes_no_files(self, mock_get_episodes, mock_get_series):
        """Test handling when episodes exist but have no files"""
        mock_get_series.return_value = {'id': 1, 'title': 'Test Series'}

        mock_get_episodes.return_value = [
            {'seasonNumber': 1, 'episodeNumber': 1, 'hasFile': False},
            {'seasonNumber': 1, 'episodeNumber': 2, 'hasFile': False},
        ]

        api = SonarrAPI()
        result = api.get_existing_episodes('Test Series')

        assert result == set()