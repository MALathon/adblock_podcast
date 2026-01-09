#!/bin/bash
# Setup script for DGX podcast processor
# Run this once on the DGX to set up the environment

set -e

WORK_DIR="${HOME}/podcast_processor"

echo "Setting up podcast processor in ${WORK_DIR}"

# Create work directory
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install faster-whisper requests

# Create directories for processing
mkdir -p raw processed

echo "Setup complete!"
echo ""
echo "To activate: source ${WORK_DIR}/venv/bin/activate"
echo "To process:  python process_podcast.py <audio_url>"
