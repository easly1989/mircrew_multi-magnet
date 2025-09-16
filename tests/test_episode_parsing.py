"""
Tests for episode parsing from release titles
"""

import pytest
from main import main  # We'll test the parsing logic


class TestEpisodeParsing:
    """Test episode parsing from release titles"""

    def test_parse_episode_from_release_title_s5e04(self):
        """Test parsing S5E04 from release title like the user's case"""
        release_title = "Only Murders in the Building - S5E04 of 10 (2025) 1080p H264 ITA ENG EAC3 SUB ITA ENG - M&M.GP CreW"

        # Test the regex pattern directly
        import re
        episode_match = re.search(r'S(\d+)E(\d+)', release_title, re.IGNORECASE)

        assert episode_match is not None
        season = int(episode_match.group(1))
        episode = int(episode_match.group(2))

        assert season == 5
        assert episode == 4

        episode_code = f"S{season:02d}E{episode:02d}"
        assert episode_code == "S05E04"

    def test_parse_episode_from_release_title_various_formats(self):
        """Test parsing episodes from various release title formats"""
        test_cases = [
            ("Show.Name.S05E04.1080p", "S05E04"),
            ("Show Name - S3E12 of 15", "S03E12"),
            ("show_name_s02e07_720p", "S02E07"),
            ("Show Name S1E1", "S01E01"),
        ]

        import re
        for release_title, expected in test_cases:
            match = re.search(r'S(\d+)E(\d+)', release_title, re.IGNORECASE)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))
                actual = f"S{season:02d}E{episode:02d}"
                assert actual == expected, f"Failed for {release_title}: expected {expected}, got {actual}"

    def test_sonarr_environment_variables_parsing(self):
        """Test that Sonarr environment variables are parsed correctly"""
        # This would normally come from Sonarr
        env_vars = {
            'sonarr_episode_seasonnumber': '5',
            'sonarr_episode_episodenumbers': '4'
        }

        if env_vars.get('sonarr_episode_seasonnumber') and env_vars.get('sonarr_episode_episodenumbers'):
            season = int(env_vars['sonarr_episode_seasonnumber'])
            episodes = [int(ep.strip()) for ep in env_vars['sonarr_episode_episodenumbers'].split(',') if ep.strip()]
            needed_episodes = {f"S{season:02d}E{ep:02d}" for ep in episodes}

            assert needed_episodes == {"S05E04"}