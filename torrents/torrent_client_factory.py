#!/usr/bin/env python3
"""
Torrent Client Factory
Factory module for creating torrent client instances based on configuration.
"""

from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from torrents.torrent_client import TorrentClient
from torrents.qbittorrent_client import QBittorrentClient


def create_torrent_client(client_type: Optional[str] = None) -> TorrentClient:
    """
    Factory function to create torrent client instances.

    Args:
        client_type (str, optional): Type of torrent client to create.
                                   If None, reads from TORRENT_CLIENT env var.
                                   Defaults to 'qbittorrent' if not specified.

    Returns:
        TorrentClient: Instance of the requested torrent client

    Raises:
        ValueError: If unsupported client type is requested
        ImportError: If required client module is not available
    """
    if client_type is None:
        client_type = os.environ.get('TORRENT_CLIENT', 'qbittorrent').lower()

    if client_type == 'qbittorrent':
        return _create_qbittorrent_client()
    else:
        raise ValueError(f"Unsupported torrent client type: {client_type}")


def _create_qbittorrent_client() -> QBittorrentClient:
    """
    Create a qBittorrent client instance.

    Returns:
        QBittorrentClient: Configured qBittorrent client instance

    Raises:
        ValueError: If required environment variables are missing
    """
    url = os.environ.get('QBITTORRENT_URL')
    username = os.environ.get('QBITTORRENT_USERNAME')
    password = os.environ.get('QBITTORRENT_PASSWORD')

    if not all([url, username, password]):
        raise ValueError(
            "Missing required qBittorrent environment variables: "
            "QBITTORRENT_URL, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD"
        )

    # Type assertions for mypy/pylance since we've verified they're not None
    assert url is not None
    assert username is not None
    assert password is not None

    return QBittorrentClient(url, username, password)


# Future client creation functions can be added here
# def _create_transmission_client() -> TransmissionClient:
#     """Create a Transmission client instance"""
#     # Implementation for Transmission client
#     pass

# def _create_deluge_client() -> DelugeClient:
#     """Create a Deluge client instance"""
#     # Implementation for Deluge client
#     pass