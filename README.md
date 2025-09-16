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

## Enhanced Pattern Matching Capabilities

The script features advanced pattern matching capabilities that intelligently parse complex TV release titles to accurately extract season and episode information. This enables reliable identification of the correct episodes from forum threads, even with varied naming conventions and languages.

### Supported Patterns

- **Standard episode format**: `"S5E04"` → `"S05E04"` (with automatic leading zero padding)
- **Season-level patterns**: `"Stagione 5"`, `"Season 2"`, `"3rd Season"`
- **Single episode patterns**: `"Ep 7"`, `"Episodio 15"`
- **Season-level search fallback**: Falls back to season-based searching when specific episode info isn't available

## Release Matching Improvements

### New Regex Pattern for Magnet Link Extraction

The extractor now uses an improved regex pattern for magnet link detection that supports various hash types and lengths:

```regex
magnet:\?xt=urn:(?:btih|ed2k):[a-fA-F0-9]{32,64}(?:&.*)?
```

**Key Improvements:**
- Supports both BitTorrent (btih) and eD2k hash types
- Handles hash lengths from 32 to 64 characters (SHA-1, SHA-256)
- Maintains backward compatibility with existing magnet formats
- More robust pattern matching for complex magnet URLs with multiple trackers

### Metadata Enhancements in Indexer Configuration

The indexer configuration has been enhanced with new metadata fields to improve extraction reliability:

```yaml
# New metadata field in mircrew.yml
forum_post_url:
  selector: a.topictitle
  attribute: href
```

**Benefits:**
- Provides direct link to forum post content
- Enables enhanced fallback mechanisms
- Improves magnet discovery success rate
- Optional field for backward compatibility

### Fallback Mechanism Workflow

The extraction process now includes a sophisticated fallback system:

1. **Primary Extraction**: Attempts improved regex pattern on thread page
2. **Enhanced Fallback**: If `forum_post_url` available, fetches specific post content
3. **Legacy Fallback**: Uses enhanced legacy extraction methods
4. **Graceful Degradation**: Handles missing metadata fields seamlessly

### Backward Compatibility Considerations

- **Automatic Detection**: Script detects availability of `forum_post_url` metadata
- **Legacy Support**: Continues working with older indexer configurations
- **Enhanced Methods**: Automatically uses improved extraction for legacy setups
- **No Breaking Changes**: Existing configurations remain fully functional

### Multi-Level Context Analysis

Episode information extraction now uses multi-level context analysis:

- Analyzes magnet element and its parent hierarchy (up to 5 levels)
- Checks sibling elements for additional context
- Combines text from multiple DOM elements
- Prioritizes most specific pattern matches
- Handles complex HTML structures and nested content

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

### Indexer Configuration Updates

#### New Metadata Field: forum_post_url

The indexer configuration now includes an optional `forum_post_url` field that provides direct access to forum post content:

**Benefits:**
- Enables enhanced fallback mechanisms for magnet extraction
- Improves reliability when primary extraction fails
- Provides more context for episode identification
- Backward compatible - existing configurations continue to work

**Configuration:**
```yaml
# Add to your mircrew.yml indexer configuration
fields:
  forum_post_url:
    selector: a.topictitle
    attribute: href
```

**Upgrade Instructions:**
1. Update your indexer configuration to include the `forum_post_url` field
2. Restart your indexer service
3. The script will automatically detect and use the new metadata
4. Existing configurations without this field will continue working with legacy methods

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

### Processing Complex Release Titles

The enhanced pattern matching and multi-level context analysis can handle complex, real-world release titles with improved accuracy:

**Input Release Title:**
```
Only Murders in the Building - S5E04 of 10 (2025) 1080p H264 ITA ENG EAC3 SUB ITA ENG - M&M.GP CreW
```

**Extracted Episode Info:** `S05E04`

**Advanced Pattern Examples:**

- **Season Pack:** `"Breaking Bad - Stagione 5 [IN CORSO]"` → `S05E00`
- **Episode with Metadata:** `"The Office S9E23 of 26 (2020) 720p"` → `S09E23`
- **Complex Format:** `"Stranger Things 4x09 The Piggyback (2022)"` → `S04E09`
- **Ordinal Season:** `"The Crown - 5th Season Episode 3"` → `S05E03`
- **Italian Format:** `"Gomorrah - Stagione 2 Episodio 7"` → `S02E07`

The script uses multi-level context analysis to extract episode information from magnet elements and their surrounding HTML structure.

### Manual Testing

You can simulate Sonarr variables for testing with complex release titles:

```bash
# Test with complex release title
export sonarr_series_title="Only Murders in the Building"
export sonarr_release_title="Only Murders in the Building - Stagione 5 Episodio 4 of 10 (2025) 1080p H264 ITA ENG"
export sonarr_episode_seasonnumber="5"
export sonarr_episode_episodenumbers="4"
python main.py

# Test season pack fallback
export sonarr_series_title="Breaking Bad"
export sonarr_release_title="Breaking Bad - Stagione 5 [IN CORSO] [03/10]"
export sonarr_episode_seasonnumber="5"
export sonarr_episode_episodenumbers="1,2,3"
python main.py
```

### Testing with Enhanced Features

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Test mode (safe testing without downloads)
export TEST_MODE=true
python tests/test_mircrew.py
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

## Testing

The project includes comprehensive test coverage to ensure reliability and accuracy of the pattern matching capabilities.

### Test Coverage

The comprehensive test suite now includes 25+ automated test cases covering all new features:

- **Episode Pattern Matching** (12 test cases):
  - Standard formats (`S5E04`, `3x12`)
  - International patterns (`Stagione 5`, `Episodio 15`)
  - Complex metadata handling with multi-level context analysis
  - Ordinal seasons (`5th Season Episode 3`)
  - Edge cases and malformatted inputs

- **Magnet Regex Pattern Testing** (8 test cases):
  - BitTorrent (btih) hash validation (32-64 characters)
  - eD2k hash support
  - Complex magnet URLs with multiple trackers
  - Invalid pattern rejection

- **Fallback Mechanism Testing** (6 test cases):
  - Primary extraction failure scenarios
  - Enhanced fallback with `forum_post_url`
  - Legacy mode compatibility
  - HTTP error handling and retries
  - Timeout and network failure recovery

- **Season Search Extraction** (8 test cases):
  - Season-based query generation with enhanced logic
  - Metadata stripping and normalization
  - Fallback mechanisms for incomplete information
  - Edge cases with multiple season patterns

- **Integration Testing**:
  - Full workflow simulation with mock components
  - End-to-end processing of real release titles
  - Backward compatibility verification
  - Error handling and recovery testing

Run the comprehensive test suite using:

```bash
# Run all tests
python -m pytest tests/test_mircrew.py -v

# Run specific test categories
python -m pytest tests/test_mircrew.py::test_episode_pattern_matching -v
python -m pytest tests/test_mircrew.py::test_fallback_mechanism -v
python -m pytest tests/test_mircrew.py::test_magnet_regex_pattern -v

# Run with coverage
python -m pytest tests/test_mircrew.py --cov=extractors.mircrew_extractor
```

The tests validate that the enhanced pattern matching, improved regex patterns, and fallback mechanisms correctly handle diverse naming conventions commonly found in torrent releases, ensuring robust episode detection across different languages and formats while maintaining full backward compatibility.

## Troubleshooting

### Release Matching and Extraction Issues

**Enhanced Fallback Mechanism Not Working**
- Verify your indexer configuration includes the `forum_post_url` field
- Check if the forum post URL is being passed correctly by Sonarr
- Enable debug logging to see fallback mechanism activation
- Ensure network connectivity allows access to individual forum posts

**Magnet Links Not Found with New Regex Pattern**
- Confirm magnet links contain valid hash formats (32-64 character hex)
- Check if magnets use supported URN types (btih or ed2k)
- Verify magnet links are properly formatted with `xt=urn:` parameter
- Test with the provided unit tests: `python -m pytest tests/test_mircrew.py::test_magnet_regex_pattern`

**Episode Pattern Matching Fails**
- Ensure release titles follow expected formats
- Check for complex metadata that might interfere with pattern matching
- Enable debug logging to see pattern matching attempts
- Test specific titles with: `python -m pytest tests/test_mircrew.py::test_episode_pattern_matching`

### Interpreting Logs Related to Fallback Mechanisms

**Primary Extraction Successful:**
```
INFO: Primary extraction successful: Found 3 magnet links
```
- Standard operation, no issues

**Enhanced Fallback Activated:**
```
INFO: New metadata available: forum_post_url present
INFO: Primary extraction failed, triggering enhanced fallback mechanism
INFO: Fetching forum post content from: https://mircrew-releases.org/viewtopic.php?t=12345
INFO: Enhanced fallback extraction successful: Found 2 magnet links
```
- Primary extraction failed, but fallback using `forum_post_url` succeeded

**Legacy Mode Activated:**
```
INFO: Legacy mode: forum_post_url not available, using backward compatible extraction
INFO: Using legacy extraction path without forum_post_url
```
- Configuration lacks `forum_post_url`, using legacy methods

**Extraction Failures:**
```
WARNING: No magnet links found after all extraction attempts
```
- All extraction methods failed, possible network or content issues

### Common Issues

**Forum Login Fails**
- Verify credentials in `.env`
- Check network connectivity to forum
- Ensure forum is not blocking your IP
- Check for CAPTCHA or additional authentication requirements

**qBittorrent Connection Issues**
- Verify WebUI is enabled and accessible
- Check credentials and URL in `.env`
- Ensure proper network configuration in Docker
- Test connection manually using qBittorrent WebUI

**No Thread Found**
- Check release title format matches forum posting conventions
- Verify forum has the expected thread
- Review search parameters in the code
- Test season-level search fallback with debug logging

**Script Runs But No Magnets Added**
- Check if episode codes are properly parsed from release titles
- Verify torrent client connectivity and permissions
- Enable debug logging to trace extraction steps
- Test with simple magnet URLs to isolate the issue

**Cookie Persistence Issues**
- Ensure write permissions for `mircrew_cookies.pkl` file
- Check file system space and permissions
- Verify the script can create/modify files in its working directory

### Debug Logging

Add these environment variables for detailed logging:

```env
LOG_LEVEL=DEBUG
```

**Debug log levels show:**
- Session verification attempts
- Pattern matching results
- Fallback mechanism activation
- HTTP request/response details
- Episode extraction analysis

### Retry Logic and Timeouts

**HTTP Request Retries:**
- Automatic retry on network failures (up to 3 attempts)
- Exponential backoff with jitter to avoid overwhelming servers
- Configurable timeout settings (default 30 seconds)

**Session Management:**
- Automatic session verification before operations
- Re-login attempts if session expires
- Cookie persistence across script runs

### Docker Network Issues

If containers can't communicate:

1. Check `docker network ls` to see available networks
2. Ensure both containers are on the same network
3. Verify container names match the URLs in configuration
4. Test network connectivity: `docker exec sonarr ping qbittorrent`

### Permission Issues

In Docker environments:

```bash
# Ensure proper permissions for cookie file
chmod 644 mircrew_cookies.pkl

# Check script directory permissions
ls -la /path/to/script/directory
```

**Common permission fixes:**
- Ensure the user running the script can write to the working directory
- Check Docker volume mount permissions
- Verify file ownership matches the container user

## Backward Compatibility

The script maintains full backward compatibility with existing Sonarr configurations that may not have newer metadata fields.

### Legacy Support Features

- **Automatic Detection**: The script automatically detects when `forum_post_url` metadata is missing
- **Legacy Extraction**: When `forum_post_url` is not available, the script uses enhanced legacy extraction methods
- **Fallback Mechanisms**: Multiple extraction strategies ensure reliable magnet discovery regardless of configuration version
- **Graceful Degradation**: Missing metadata fields are handled gracefully with appropriate defaults

### Configuration Requirements

For optimal performance, update your indexer configuration to include the `forum_post_url` field. However, the script will continue to work with older configurations that lack this field.

### Migration Notes

- Existing configurations without `forum_post_url` will continue to work
- Enhanced extraction methods are used automatically for legacy configurations
- No configuration changes are required for existing users
- New installations should include `forum_post_url` for improved reliability

## Security Notes

- Store credentials securely (use Docker secrets or environment files)
- Cookie files contain session information - handle carefully
- Consider using VPN if accessing forums from restricted networks
- Regularly update passwords and review access logs

## Changelog

### v2.1.0 - Release Matching Improvements (2025-01-XX)

**New Features:**
- **Enhanced Regex Patterns**: Improved magnet link extraction supporting btih and ed2k hash types (32-64 characters)
- **Metadata Enhancements**: Added `forum_post_url` field to indexer configuration for better extraction reliability
- **Fallback Mechanism**: Sophisticated multi-stage extraction with enhanced backward compatibility
- **Multi-Level Context Analysis**: Advanced episode information extraction from HTML structure
- **Retry Logic**: Automatic retry on HTTP failures with exponential backoff

**Improvements:**
- **Episode Pattern Matching**: Extended support for complex release titles and international formats
- **Season Search Extraction**: Enhanced logic for season-level fallback searching
- **Comprehensive Testing**: 25+ automated test cases covering all new features
- **Debug Logging**: Detailed logging for troubleshooting fallback mechanisms
- **Error Handling**: Improved error recovery and session management

**Technical Details:**
- Backward compatible with existing configurations
- Automatic detection of new metadata fields
- Graceful degradation when features unavailable
- No breaking changes to existing workflows

**Files Modified:**
- `extractors/mircrew_extractor.py` - Core extraction improvements
- `sonarr_indexers/mircrew.yml` - New metadata field configuration
- `tests/test_mircrew.py` - Comprehensive test coverage
- `README.md` - Updated documentation

### Previous Versions

- **v2.0.0** - Modular architecture implementation
- **v1.x** - Initial release with basic forum extraction

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