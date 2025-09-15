#!/bin/sh

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

# Install requests if not present
check_python_module requests || pip3 install --no-cache-dir --break-system-packages  requests

# Install beautifulsoup4 if not present
check_python_module bs4 || pip3 install --no-cache-dir --break-system-packages  beautifulsoup4

# Now run the Python script, after ensuring you are in the correct directory
cd "$(dirname "$0")"
python3 main.py
