#!/bin/sh

# Enable error handling - exit on any error
set -e

# Debug: Check environment variables
echo "=== Script started at $(date) ===" >&2
echo "Debug: sonarr_eventtype = '$sonarr_eventtype'" >&2
echo "Debug: Current working directory: $(pwd)" >&2
echo "Debug: Script path: $0" >&2
echo "Debug: Available environment variables:" >&2
env | grep -i sonarr >&2 || echo "No sonarr environment variables found" >&2

# Set up local Python package directory
echo "Setting up script directory..." >&2
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Script directory: $SCRIPT_DIR" >&2
LOCAL_LIB="$SCRIPT_DIR/local_lib"
echo "Local lib directory: $LOCAL_LIB" >&2
export PYTHONPATH="$LOCAL_LIB:$PYTHONPATH"
echo "PYTHONPATH set to: $PYTHONPATH" >&2

# Create local lib directory if it doesn't exist
echo "Creating local lib directory..." >&2
if ! mkdir -p "$LOCAL_LIB"; then
    echo "ERROR: Failed to create directory $LOCAL_LIB" >&2
    echo "Current permissions: $(ls -la "$(dirname "$LOCAL_LIB")" 2>/dev/null || echo 'cannot list parent directory')" >&2
    exit 1
fi
echo "✓ Local lib directory created successfully" >&2

# Check if python3 is available
echo "Checking for python3..." >&2
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH!" >&2
    echo "Available Python versions:" >&2
    command -v python >&2 || echo "python not found" >&2
    command -v python2 >&2 || echo "python2 not found" >&2
    command -v python3 >&2 || echo "python3 not found" >&2
    echo "PATH: $PATH" >&2
    exit 1
fi
echo "✓ python3 found: $(python3 --version 2>&1 || echo 'version check failed')" >&2

# Check if pip3 is available
echo "Checking for pip3..." >&2
if ! command -v pip3 >/dev/null 2>&1; then
    echo "pip3 not found, attempting to install..." >&2
    echo "Running: apk add --no-cache py3-pip" >&2
    if ! apk add --no-cache py3-pip; then
        echo "ERROR: Failed to install pip3" >&2
        echo "Available package managers:" >&2
        command -v apk >&2 || echo "apk not found" >&2
        command -v apt >&2 || echo "apt not found" >&2
        command -v yum >&2 || echo "yum not found" >&2
        exit 1
    fi
fi
echo "✓ pip3 found: $(pip3 --version 2>&1 || echo 'version check failed')" >&2

# Function to verify if a Python module is installed
check_python_module() {
    echo "Checking if Python module '$1' is installed..." >&2
    if python3 -c "import $1" >/dev/null 2>&1; then
        echo "✓ Module '$1' is already installed" >&2
        return 0
    else
        echo "✗ Module '$1' is not installed" >&2
        return 1
    fi
}

# Function to install package with error handling
install_package() {
    local package=$1
    local module=$2
    echo "Installing $package (for module $module)..." >&2
    if pip3 install --target="$LOCAL_LIB" --upgrade --no-cache-dir "$package"; then
        echo "✓ Successfully installed $package" >&2
        return 0
    else
        echo "ERROR: Failed to install $package" >&2
        return 1
    fi
}

# Install packages to local directory if not present
echo "=== Checking and installing required packages ===" >&2
check_python_module requests || install_package requests requests || exit 1
check_python_module bs4 || install_package beautifulsoup4 bs4 || exit 1
check_python_module dotenv || install_package python-dotenv dotenv || exit 1
echo "=== Package installation completed ===" >&2

# Now run the Python script, after ensuring you are in the correct directory
echo "=== Preparing to execute Python script ===" >&2
echo "Changing to script directory: $SCRIPT_DIR" >&2
if ! cd "$SCRIPT_DIR"; then
    echo "ERROR: Failed to change to script directory $SCRIPT_DIR" >&2
    exit 1
fi
echo "✓ Successfully changed to script directory" >&2
echo "Current directory: $(pwd)" >&2
echo "Contents of current directory:" >&2
ls -la >&2 || echo "Cannot list directory contents" >&2

# Log the event type for debugging
echo "Sonarr Event Type: '$sonarr_eventtype'" >&2

if [ "$sonarr_eventtype" = "Test" ]; then
    echo "=== TEST MODE DETECTED ===" >&2
    echo "Checking pytest..." >&2
    check_python_module pytest || install_package pytest pytest || exit 1
    echo "Running tests with pytest..." >&2
    if python3 -m pytest tests/test_mircrew.py -v; then
        echo "✓ Test execution completed successfully" >&2
    else
        echo "ERROR: Test execution failed" >&2
        exit 1
    fi
else
    echo "=== RUNNING MAIN SCRIPT ===" >&2
    echo "Checking if main.py exists..." >&2
    if [ -f "main.py" ]; then
        echo "✓ main.py found" >&2
        echo "Running main script..." >&2
        if python3 main.py; then
            echo "✓ Main script execution completed successfully" >&2
        else
            echo "ERROR: Main script execution failed" >&2
            exit 1
        fi
    else
        echo "ERROR: main.py not found in current directory" >&2
        echo "Files in current directory:" >&2
        ls -la *.py >&2 || echo "No Python files found" >&2
        exit 1
    fi
fi

echo "=== Script execution completed at $(date) ===" >&2
