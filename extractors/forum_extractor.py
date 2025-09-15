#!/usr/bin/env python3
"""
Generic Forum Extractor Interface
This module defines the abstract interface for forum extractor implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from torrents.torrent_client import TorrentClient


class ForumExtractor(ABC):
    """
    Abstract base class for forum extractor implementations.

    This interface allows the main script to work with any forum site
    by implementing these standard methods.
    """

    def __init__(self, torrent_client: TorrentClient):
        """
        Initialize the forum extractor with a torrent client.

        Args:
            torrent_client (TorrentClient): The torrent client to use for operations
        """
        self.torrent_client = torrent_client
        self.session = None  # Will be set by concrete implementations

    @abstractmethod
    def login(self, retries: int = 15, initial_wait: int = 5) -> bool:
        """
        Login to the forum site.

        Args:
            retries (int): Number of login retry attempts
            initial_wait (int): Initial wait time between retries

        Returns:
            bool: True if login successful, False otherwise
        """
        pass

    @abstractmethod
    def verify_session(self) -> bool:
        """
        Verify if the current session is still valid.

        Returns:
            bool: True if session is valid, False otherwise
        """
        pass

    @abstractmethod
    def search_thread_by_release_title(self, release_title: str) -> Optional[str]:
        """
        Search for a thread by release title.

        Args:
            release_title (str): The release title to search for

        Returns:
            str or None: URL of the found thread, or None if not found
        """
        pass

    @abstractmethod
    def extract_magnets_from_thread(self, thread_url: str) -> List[Dict[str, Any]]:
        """
        Extract all magnet links from a thread.

        Args:
            thread_url (str): URL of the thread to extract magnets from

        Returns:
            List[Dict[str, Any]]: List of magnet information dictionaries
                                 Each dict should contain at least:
                                 - 'magnet': magnet URL
                                 - 'episode_info': episode information string
                                 - 'magnet_title': title from magnet
        """
        pass

    @abstractmethod
    def extract_episode_info(self, magnet_element) -> str:
        """
        Extract episode information from a magnet element.

        Args:
            magnet_element: The HTML element containing magnet information

        Returns:
            str: Episode information (e.g., "S01E05")
        """
        pass

    @abstractmethod
    def extract_episode_codes(self, magnet_title: str) -> set:
        """
        Extract episode codes from magnet title.

        Args:
            magnet_title (str): Title extracted from magnet link

        Returns:
            set: Set of episode codes found (e.g., {"S01E05", "S01E06"})
        """
        pass

    @abstractmethod
    def find_original_torrent(self, original_torrents: List[Dict[str, Any]], target_magnet_hash: str) -> Optional[Dict[str, Any]]:
        """
        Find the original torrent that matches a magnet hash.

        Args:
            original_torrents (List[Dict[str, Any]]): List of torrents from client
            target_magnet_hash (str): Hash to search for

        Returns:
            Dict or None: Matching torrent info, or None if not found
        """
        pass

    @abstractmethod
    def parse_needed_episodes(self, episode_path: str) -> set:
        """
        Parse episode information from file path.

        Args:
            episode_path (str): File path containing episode information

        Returns:
            set: Set of needed episode codes
        """
        pass