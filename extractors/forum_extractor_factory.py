#!/usr/bin/env python3
"""
Forum Extractor Factory
Factory module for creating forum extractor instances based on configuration.
"""

from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.forum_extractor import ForumExtractor
from extractors.mircrew_extractor import MIRCrewExtractor
from torrents.torrent_client_factory import create_torrent_client


def create_forum_extractor(forum_type: Optional[str] = None) -> ForumExtractor:
    """
    Factory function to create forum extractor instances.

    Args:
        forum_type (str, optional): Type of forum extractor to create.
                                   If None, reads from FORUM_TYPE env var.
                                   Defaults to 'mircrew' if not specified.

    Returns:
        ForumExtractor: Instance of the requested forum extractor

    Raises:
        ValueError: If unsupported forum type is requested
    """
    if forum_type is None:
        forum_type = os.environ.get('FORUM_TYPE', 'mircrew').lower()

    if forum_type == 'mircrew':
        return _create_mircrew_extractor()
    else:
        raise ValueError(f"Unsupported forum type: {forum_type}")


def _create_mircrew_extractor() -> MIRCrewExtractor:
    """
    Create a MIRCrew forum extractor instance.

    Returns:
        MIRCrewExtractor: Configured MIRCrew extractor instance
    """
    # Get the torrent client that will be used by the forum extractor
    torrent_client = create_torrent_client()
    return MIRCrewExtractor(torrent_client)


# Future forum extractor creation functions can be added here
# def _create_other_forum_extractor() -> OtherForumExtractor:
#     """Create another forum extractor instance"""
#     # Implementation for other forum types
#     pass