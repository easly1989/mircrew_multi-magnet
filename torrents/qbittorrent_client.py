#!/usr/bin/env python3
"""
qBittorrent Client Implementation
Concrete implementation of TorrentClient for qBittorrent WebUI.
"""

import requests
import re
import logging
from typing import Optional, List, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from torrents.torrent_client import TorrentClient

logger = logging.getLogger(__name__)


class QBittorrentClient(TorrentClient):
    """
    qBittorrent WebUI client implementation.

    This class handles all interactions with qBittorrent WebUI API.
    """

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize the qBittorrent client.

        Args:
            url (str): qBittorrent WebUI URL (e.g., "http://localhost:8080")
            username (str): qBittorrent username
            password (str): qBittorrent password
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.cookie = None

    def login(self) -> bool:
        """
        Login to qBittorrent WebUI.

        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            login_url = f"{self.url}/api/v2/auth/login"
            data = {
                'username': self.username,
                'password': self.password
            }
            resp = requests.post(login_url, data=data)
            if resp.text == "Ok.":
                self.cookie = resp.cookies
                logger.info("qBittorrent login successful")
                return True
            else:
                logger.error("qBittorrent login failed")
                return False
        except Exception as e:
            logger.error(f"Error logging into qBittorrent: {e}")
            return False

    def add_magnet(self, magnet_url: str, category: Optional[str] = None) -> bool:
        """
        Add a magnet link to qBittorrent.

        Args:
            magnet_url (str): The magnet URL to add
            category (str, optional): Category to assign to the torrent

        Returns:
            bool: True if magnet added successfully, False otherwise
        """
        try:
            url = f"{self.url}/api/v2/torrents/add"
            data = {
                'urls': magnet_url,
            }
            if category:
                data['category'] = category
            resp = requests.post(url, data=data, cookies=self.cookie)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Error adding magnet: {e}")
            return False

    def get_torrents(self) -> List[Dict[str, Any]]:
        """
        Get list of torrents from qBittorrent.

        Returns:
            List[Dict[str, Any]]: List of torrent information dictionaries
        """
        try:
            url = f"{self.url}/api/v2/torrents/info"
            resp = requests.get(url, cookies=self.cookie)
            return resp.json()
        except Exception as e:
            logger.error(f"Error retrieving qBittorrent torrents: {e}")
            return []

    def remove_torrent(self, torrent_hash: str) -> bool:
        """
        Remove a torrent from qBittorrent.

        Args:
            torrent_hash (str): Hash of the torrent to remove

        Returns:
            bool: True if torrent removed successfully, False otherwise
        """
        try:
            url = f"{self.url}/api/v2/torrents/delete"
            data = {
                'hashes': torrent_hash,
                'deleteFiles': 'false'
            }
            resp = requests.post(url, data=data, cookies=self.cookie)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Error removing torrent: {e}")
            return False

    def get_torrent_hash_from_magnet(self, magnet_url: str) -> Optional[str]:
        """
        Extract torrent hash from magnet URL.

        Args:
            magnet_url (str): The magnet URL to parse

        Returns:
            str or None: The torrent hash if found, None otherwise
        """
        try:
            # Try 40-character hash first
            match = re.search(r'urn:btih:([a-fA-F0-9]{40})', magnet_url)
            if match:
                return match.group(1).lower()

            # Try 32-character hash
            match = re.search(r'urn:btih:([a-fA-F0-9]{32})', magnet_url)
            if match:
                return match.group(1).lower()

            return None
        except Exception as e:
            logger.error(f"Error extracting hash: {e}")
            return None