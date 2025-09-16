#!/bin/sh

# Enable error handling - exit on any error
set -e

# Script started
echo "=== Multi-Forum Multi-Magnet Script Started ==="

# Set up local Python package directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_LIB="$SCRIPT_DIR/local_lib"
export PYTHONPATH="$LOCAL_LIB:$PYTHONPATH"

# Create local lib directory if it doesn't exist
if ! mkdir -p "$LOCAL_LIB"; then
    echo "ERROR: Failed to create directory $LOCAL_LIB" >&2
    exit 1
fi

# Check if python3 is available
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH!" >&2
    exit 1
fi

# Check if pip3 is available
if ! command -v pip3 >/dev/null 2>&1; then
    if ! apk add --no-cache py3-pip; then
        echo "ERROR: Failed to install pip3" >&2
        exit 1
    fi
fi

# Function to install package with error handling
install_package() {
    local package=$1
    local module=$2
    if pip3 install --target="$LOCAL_LIB" --upgrade --no-cache-dir "$package"; then
        return 0
    else
        echo "ERROR: Failed to install $package" >&2
        return 1
    fi
}

# Install core packages
echo "Installing required packages..."
python3 -c "import requests" 2>/dev/null || install_package requests requests || exit 1
python3 -c "import bs4" 2>/dev/null || install_package beautifulsoup4 bs4 || exit 1
python3 -c "import dotenv" 2>/dev/null || install_package python-dotenv dotenv || exit 1

# Change to script directory
cd "$SCRIPT_DIR"

if [ "$sonarr_eventtype" = "Test" ]; then
    echo "Running tests..."
    python3 -c "import pytest" 2>/dev/null || install_package pytest pytest || exit 1
    python3 -c "import pytest_mock" 2>/dev/null || install_package pytest-mock pytest_mock || exit 1
    if ! python3 -m pytest tests/test_mircrew.py -v; then
        echo "ERROR: Test execution failed" >&2
        exit 1
    fi
else
    echo "Running main script..."
    if [ ! -f "main.py" ]; then
        echo "ERROR: main.py not found" >&2
        exit 1
    fi
    if ! python3 main.py; then
        echo "ERROR: Main script execution failed" >&2
        exit 1
    fi
fi

echo "Script completed successfully"
