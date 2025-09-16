#!/bin/sh

# Debug: Check environment variables
echo "Debug: sonarr_eventtype = '$sonarr_eventtype'"
env | grep -i sonarr >&1

# Set up local Python package directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_LIB="$SCRIPT_DIR/local_lib"
export PYTHONPATH="$LOCAL_LIB:$PYTHONPATH"

# Create local lib directory if it doesn't exist
mkdir -p "$LOCAL_LIB"

# Check if python3 is available
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found in PATH!"
    exit 1
fi

# Check if pip3 is available
if ! command -v pip3 >/dev/null 2>&1; then
    echo "pip3 not found, installing..."
    apk add --no-cache py3-pip
    if [ $? -ne 0 ]; then
        echo "Error installing pip3"
        exit 1
    fi
fi

# Function to verify if a Python module is installed
check_python_module() {
    python3 -c "import $1" >/dev/null 2>&1
    return $?
}

# Install packages to local directory if not present
echo "Checking and installing requests..."
check_python_module requests || (echo "Installing requests..." && pip3 install --target="$LOCAL_LIB" --upgrade --no-cache-dir requests)
echo "Checking and installing beautifulsoup4..."
check_python_module bs4 || (echo "Installing beautifulsoup4..." && pip3 install --target="$LOCAL_LIB" --upgrade --no-cache-dir beautifulsoup4)
echo "Checking and installing python-dotenv..."
check_python_module dotenv || (echo "Installing python-dotenv..." && pip3 install --target="$LOCAL_LIB" --upgrade --no-cache-dir python-dotenv)

# Now run the Python script, after ensuring you are in the correct directory
cd "$SCRIPT_DIR"

# Log the event type for debugging
echo "Sonarr Event Type: $sonarr_eventtype"

if [ "$sonarr_eventtype" = "Test" ]; then
    echo "Test mode detected. Checking pytest..."
    check_python_module pytest || (echo "Installing pytest..." && pip3 install --target="$LOCAL_LIB" --upgrade --no-cache-dir pytest)
    echo "Running tests with pytest..."
    python3 -m pytest tests/test_mircrew.py -v
    echo "Test execution completed."
else
    echo "Running main script..."
    python3 main.py
fi
