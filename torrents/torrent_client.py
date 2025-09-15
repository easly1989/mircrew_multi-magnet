#!/usr/bin/env python3
"""
Generic Torrent Client Interface
This module defines the abstract interface for torrent client implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class TorrentClient(ABC):
    """
    Abstract base class for torrent client implementations.

    This interface allows the main script to work with any torrent client
    by implementing these standard methods.
    """

    @abstractmethod
    def login(self) -> bool:
        """
        Authenticate with the torrent client.

        Returns:
            bool: True if login successful, False otherwise
        """
        pass

    @abstractmethod
    def add_magnet(self, magnet_url: str, category: Optional[str] = None) -> bool:
        """
        Add a magnet link to the torrent client.

        Args:
            magnet_url (str): The magnet URL to add
            category (str, optional): Category to assign to the torrent

        Returns:
            bool: True if magnet added successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_torrents(self) -> List[Dict[str, Any]]:
        """
        Get list of torrents from the client.

        Returns:
            List[Dict[str, Any]]: List of torrent information dictionaries
        """
        pass

    @abstractmethod
    def remove_torrent(self, torrent_hash: str) -> bool:
        """
        Remove a torrent from the client.

        Args:
            torrent_hash (str): Hash of the torrent to remove

        Returns:
            bool: True if torrent removed successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_torrent_hash_from_magnet(self, magnet_url: str) -> Optional[str]:
        """
        Extract torrent hash from magnet URL.

        Args:
            magnet_url (str): The magnet URL to parse

        Returns:
            str or None: The torrent hash if found, None otherwise
        """
        pass