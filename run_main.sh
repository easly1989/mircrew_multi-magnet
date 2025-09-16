#!/bin/sh

# Enable error handling - exit on any error
set -e

# Debug: Check environment variables
echo "=== Script started at $(date) ==="
echo "Debug: sonarr_eventtype = '$sonarr_eventtype'"
echo "Debug: Current working directory: $(pwd)"
echo "Debug: Script path: $0"
echo "Debug: Available environment variables:"
env | grep -i sonarr || echo "No sonarr environment variables found"

# Set up local Python package directory
echo "Setting up script directory..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Script directory: $SCRIPT_DIR"
LOCAL_LIB="$SCRIPT_DIR/local_lib"
echo "Local lib directory: $LOCAL_LIB"
export PYTHONPATH="$LOCAL_LIB:$PYTHONPATH"
echo "PYTHONPATH set to: $PYTHONPATH"

# Create local lib directory if it doesn't exist
echo "Creating local lib directory..."
if ! mkdir -p "$LOCAL_LIB"; then
    echo "ERROR: Failed to create directory $LOCAL_LIB"
    echo "Current permissions: $(ls -la "$(dirname "$LOCAL_LIB")" 2>/dev/null || echo 'cannot list parent directory')"
    exit 1
fi
echo "✓ Local lib directory created successfully"

# Check if python3 is available
echo "Checking for python3..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH!"
    echo "Available Python versions:"
    command -v python || echo "python not found"
    command -v python2 || echo "python2 not found"
    command -v python3 || echo "python3 not found"
    echo "PATH: $PATH"
    exit 1
fi
echo "✓ python3 found: $(python3 --version 2>&1 || echo 'version check failed')"

# Check if pip3 is available
echo "Checking for pip3..."
if ! command -v pip3 >/dev/null 2>&1; then
    echo "pip3 not found, attempting to install..."
    echo "Running: apk add --no-cache py3-pip"
    if ! apk add --no-cache py3-pip; then
        echo "ERROR: Failed to install pip3"
        echo "Available package managers:"
        command -v apk || echo "apk not found"
        command -v apt || echo "apt not found"
        command -v yum || echo "yum not found"
        exit 1
    fi
fi
echo "✓ pip3 found: $(pip3 --version 2>&1 || echo 'version check failed')"

# Function to verify if a Python module is installed
check_python_module() {
    echo "Checking if Python module '$1' is installed..."
    if python3 -c "import $1" >/dev/null 2>&1; then
        echo "✓ Module '$1' is already installed"
        return 0
    else
        echo "✗ Module '$1' is not installed"
        return 1
    fi
}

# Function to install package with error handling
install_package() {
    local package=$1
    local module=$2
    echo "Installing $package (for module $module)..."
    if pip3 install --target="$LOCAL_LIB" --upgrade --no-cache-dir "$package"; then
        echo "✓ Successfully installed $package"
        return 0
    else
        echo "ERROR: Failed to install $package"
        return 1
    fi
}

# Install packages to local directory if not present
echo "=== Checking and installing required packages ==="
check_python_module requests || install_package requests requests || exit 1
check_python_module bs4 || install_package beautifulsoup4 bs4 || exit 1
check_python_module dotenv || install_package python-dotenv dotenv || exit 1
echo "=== Package installation completed ==="

# Now run the Python script, after ensuring you are in the correct directory
echo "=== Preparing to execute Python script ==="
echo "Changing to script directory: $SCRIPT_DIR"
if ! cd "$SCRIPT_DIR"; then
    echo "ERROR: Failed to change to script directory $SCRIPT_DIR"
    exit 1
fi
echo "✓ Successfully changed to script directory"
echo "Current directory: $(pwd)"
echo "Contents of current directory:"
ls -la || echo "Cannot list directory contents"

# Log the event type for debugging
echo "Sonarr Event Type: '$sonarr_eventtype'"

if [ "$sonarr_eventtype" = "Test" ]; then
    echo "=== TEST MODE DETECTED ==="
    echo "Checking pytest..."
    check_python_module pytest || install_package pytest pytest || exit 1
    echo "Running tests with pytest..."
    if python3 -m pytest tests/test_mircrew.py -v; then
        echo "✓ Test execution completed successfully"
    else
        echo "ERROR: Test execution failed"
        exit 1
    fi
else
    echo "=== RUNNING MAIN SCRIPT ==="
    echo "Checking if main.py exists..."
    if [ -f "main.py" ]; then
        echo "✓ main.py found"
        echo "Running main script..."
        if python3 main.py; then
            echo "✓ Main script execution completed successfully"
        else
            echo "ERROR: Main script execution failed"
            exit 1
        fi
    else
        echo "ERROR: main.py not found in current directory"
        echo "Files in current directory:"
        ls -la *.py || echo "No Python files found"
        exit 1
    fi
fi

echo "=== Script execution completed at $(date) ==="
