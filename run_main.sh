#!/bin/sh

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
check_python_module requests || pip3 install --target="$LOCAL_LIB" --no-cache-dir requests
check_python_module bs4 || pip3 install --target="$LOCAL_LIB" --no-cache-dir beautifulsoup4
check_python_module dotenv || pip3 install --target="$LOCAL_LIB" --no-cache-dir python-dotenv

# Now run the Python script, after ensuring you are in the correct directory
cd "$SCRIPT_DIR"
if [ "$EventType" = "Test" ]; then
    python3 tests/test_mircrew.py
else
    python3 main.py
fi
