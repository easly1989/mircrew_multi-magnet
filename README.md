# Multi-Forum Multi-Magnet Script for Sonarr

A powerful, modular Python script that automatically downloads TV episodes from forum threads and integrates seamlessly with Sonarr. Designed specifically for users running Sonarr in Docker environments.

## If you like my work
Help me pay off my home loan → [Donate on PayPal](https://paypal.me/ruggierocarlo)

## Features

- **Modular Architecture**: Support for multiple forums and torrent clients through clean interfaces
- **Sonarr Integration**: Automatically processes episodes based on Sonarr's post-processing variables
- **Smart Episode Detection**: Intelligently identifies and downloads only the episodes you need
- **Cookie Persistence**: Maintains forum sessions between runs for better reliability
- **Docker-Friendly**: Optimized for containerized environments
- **Test Mode**: Safe testing without making actual changes
- **Multi-Client Support**: Extensible to work with different torrent clients

## Prerequisites

- Python 3.7+
- Access to a forum site (currently supports MIRCrew)
- A torrent client with WebUI (currently supports qBittorrent)
- Sonarr configured and running (preferably in Docker)

### Dependencies

```bash
pip install requests beautifulsoup4 python-dotenv
```

## Quick Start with Docker Sonarr

### 1. Prepare Your Environment

Create a `.env` file in the project root:

```env
# Forum Configuration (MIRCrew)
FORUM_TYPE=mircrew
MIRCREW_BASE_URL=https://mircrew-releases.org/
MIRCREW_USERNAME=your_forum_username
MIRCREW_PASSWORD=your_forum_password

# Torrent Client Configuration (qBittorrent)
TORRENT_CLIENT=qbittorrent
QBITTORRENT_URL=http://qbittorrent:8080
QBITTORRENT_USERNAME=your_qbittorrent_username
QBITTORRENT_PASSWORD=your_qbittorrent_password
```

### 2. Docker Compose Setup

If running Sonarr in Docker, your `docker-compose.yml` should look like this:

```yaml
version: '3.8'
services:
  sonarr:
    image: linuxserver/sonarr:latest
    container_name: sonarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Rome
    volumes:
      - ./config/sonarr:/config
      - ./downloads:/downloads
      - ./tv:/tv
      - /path/to/script:/scripts  # Mount script directory
    ports:
      - "8989:8989"
    restart: unless-stopped
    depends_on:
      - qbittorrent

  qbittorrent:
    image: linuxserver/qbittorrent:latest
    container_name: qbittorrent
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Rome
      - WEBUI_PORT=8080
    volumes:
      - ./config/qbittorrent:/config
      - ./downloads:/downloads
    ports:
      - "8080:8080"
      - "6881:6881"
      - "6881:6881/udp"
    restart: unless-stopped

  # Optional: Add the script as a service for easier management
  mircrew-script:
    build: .
    container_name: mircrew-script
    environment:
      - FORUM_TYPE=mircrew
      - MIRCREW_BASE_URL=https://mircrew-releases.org/
      - MIRCREW_USERNAME=${MIRCREW_USERNAME}
      - MIRCREW_PASSWORD=${MIRCREW_PASSWORD}
      - TORRENT_CLIENT=qbittorrent
      - QBITTORRENT_URL=http://qbittorrent:8080
      - QBITTORRENT_USERNAME=${QBITTORRENT_USERNAME}
      - QBITTORRENT_PASSWORD=${QBITTORRENT_PASSWORD}
    volumes:
      - ./mircrew_cookies.pkl:/app/mircrew_cookies.pkl
    depends_on:
      - qbittorrent
    command: python main.py
```

### 3. Dockerfile for the Script

Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the script
CMD ["python", "main.py"]
```

Create `requirements.txt`:

```
requests==2.31.0
beautifulsoup4==4.12.2
python-dotenv==1.0.0
```

### 4. Configure Sonarr

1. **Add Custom Script**: In Sonarr settings, go to `Connect` → `+` → `Custom Script`
2. **Script Path**: Set to `/scripts/main.py` (or wherever you mounted the script)
3. **Script Settings**:
   - On Grab: No
   - On Download: Yes
   - On Upgrade: Yes
   - On Rename: No
4. **Arguments**: Leave empty (script reads from environment variables)

### 5. Test the Setup

Run a test episode download:

```bash
# In test mode (won't actually download)
python tests/test_mircrew.py

# Or run the main script directly
python main.py
```
## Alternative: Using Shell Script for Non-Modifiable Docker Setups

For users who cannot modify their Docker Compose files (e.g., when using managed setups like Saltbox), you can use the provided `run_main.sh` shell script that automatically handles Python dependencies and runs the main script.

### Prerequisites

- Python 3.7+ installed on the host system
- Access to bash/shell
- The script directory accessible by Sonarr

### Setup Steps

1. **Place the Script**: Copy `run_main.sh` to a directory accessible by Sonarr, e.g., `/opt/scripts/`. Ensure the entire project directory is available there.

2. **Make Executable**: `chmod +x /opt/scripts/run_main.sh`

3. **Configure Environment**: Create/update `.env` file in the same directory as the script with your credentials (see Environment Variables section above).

4. **Configure Sonarr**: In Sonarr settings, add a Custom Script pointing to `/opt/scripts/run_main.sh` instead of `main.py`. Use the same settings as described in the Docker section.

5. **Test**: Run the script manually to ensure it works:

   ```bash
   /opt/scripts/run_main.sh
   ```

**Important Notes**:

- The script will automatically install required Python packages (requests, beautifulsoup4) if they're not present using `pip3`.
- The script assumes an Alpine-based system for installing pip3 if missing. If using a different Linux distribution (e.g., Ubuntu/Debian in Saltbox), ensure `python3` and `pip3` are installed manually:
  ```bash
  sudo apt update
  sudo apt install python3 python3-pip
  ```
- The script changes to the script's directory and runs `python3 main.py`, so ensure `main.py` is in the same directory as `run_main.sh`.
- The Sonarr user must have read and write access to the script directory and all its files and subdirectories.
- When configuring the Custom Script in Sonarr, ensure the path points to `run_main.sh` instead of `main.py`.

This setup allows you to use the script without modifying Docker configurations.

## Configuration Details

### Environment Variables

#### Forum Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `FORUM_TYPE` | Type of forum to use | `mircrew` | No |
| `MIRCREW_BASE_URL` | MIRCrew forum URL | `https://mircrew-releases.org/` | Yes |
| `MIRCREW_USERNAME` | Your forum username | - | Yes |
| `MIRCREW_PASSWORD` | Your forum password | - | Yes |

#### Torrent Client Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TORRENT_CLIENT` | Type of torrent client | `qbittorrent` | No |
| `QBITTORRENT_URL` | qBittorrent WebUI URL | - | Yes |
| `QBITTORRENT_USERNAME` | qBittorrent username | - | Yes |
| `QBITTORRENT_PASSWORD` | qBittorrent password | - | Yes |

#### Sonarr Integration Variables

These are automatically provided by Sonarr when the script runs:

- `sonarr_series_title`: Name of the TV series
- `sonarr_episodefile_relativepath`: Relative path to the downloaded episode file
- `sonarr_release_title`: Release title that triggered the download
- `sonarr_episode_seasonnumber`: Season number
- `sonarr_episode_episodenumbers`: Episode numbers

### Network Configuration

For Docker environments:

- Ensure containers can communicate (use container names as hostnames)
- qBittorrent should be accessible at `http://qbittorrent:8080` from Sonarr's perspective
- The script should have network access to both the forum and qBittorrent

## How It Works

1. **Episode Processing**: Sonarr runs the script after downloading an episode
2. **Thread Search**: Script searches the forum for a thread matching the release title
3. **Magnet Extraction**: Extracts all magnet links from the found thread
4. **Episode Filtering**: Identifies which magnets correspond to needed episodes
5. **Smart Downloading**: Adds only the required magnets to your torrent client
6. **Cleanup**: Optionally removes the original torrent if all episodes are now available

## Usage Examples

### Basic Usage

```bash
python main.py
```

The script will automatically read Sonarr's environment variables and process accordingly.

### Test Mode

```bash
python tests/test_mircrew.py
```

This allows you to test the script without making actual changes to your torrent client.

### Manual Testing

You can simulate Sonarr variables for testing:

```bash
export sonarr_series_title="Breaking Bad"
export sonarr_release_title="Breaking.Bad.S05E01.720p.HDTV.x264"
export sonarr_episode_seasonnumber="5"
export sonarr_episode_episodenumbers="1"
python main.py
```

## Architecture

The script uses a clean, modular architecture:

```
main.py
├── extractors/
│   ├── forum_extractor.py (Interface)
│   ├── mircrew_extractor.py (MIRCrew implementation)
│   └── forum_extractor_factory.py (Factory)
├── torrents/
│   ├── torrent_client.py (Interface)
│   ├── qbittorrent_client.py (qBittorrent implementation)
│   └── torrent_client_factory.py (Factory)
└── tests/
    └── test_mircrew.py (Test script)
```

### Adding New Forums

To add support for a new forum:

1. Create a new extractor implementing `ForumExtractor`
2. Add factory function in `forum_extractor_factory.py`
3. Set `FORUM_TYPE` environment variable

### Adding New Torrent Clients

To add support for a new torrent client:

1. Create a new client implementing `TorrentClient`
2. Add factory function in `torrent_client_factory.py`
3. Set `TORRENT_CLIENT` environment variable

## Troubleshooting

### Common Issues

**Forum Login Fails**
- Verify credentials in `.env`
- Check network connectivity to forum
- Ensure forum is not blocking your IP

**qBittorrent Connection Issues**
- Verify WebUI is enabled and accessible
- Check credentials and URL in `.env`
- Ensure proper network configuration in Docker

**No Thread Found**
- Check release title format
- Verify forum has the expected thread
- Review search parameters in the code

**Script Runs But No Magnets Added**
- Check if episode codes are properly parsed
- Verify torrent client connectivity
- Enable debug logging

### Debug Logging

Add these environment variables for detailed logging:

```env
LOG_LEVEL=DEBUG
```

### Docker Network Issues

If containers can't communicate:

1. Check `docker network ls` to see available networks
2. Ensure both containers are on the same network
3. Verify container names match the URLs in configuration

### Permission Issues

In Docker environments:

```bash
# Ensure proper permissions for cookie file
chmod 644 mircrew_cookies.pkl
```

## Security Notes

- Store credentials securely (use Docker secrets or environment files)
- Cookie files contain session information - handle carefully
- Consider using VPN if accessing forums from restricted networks
- Regularly update passwords and review access logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Adding New Features

- Follow the existing interface patterns
- Add comprehensive tests
- Update documentation
- Maintain backward compatibility

## License

This project is open source. Please check the license file for details.

## Support

- Check the troubleshooting section above
- Review Docker and Sonarr documentation
- Test with the provided test scripts
- Enable debug logging for detailed error information

---

**Note**: This script is designed for personal use with legal content. Always respect copyright laws and terms of service of the websites you access.