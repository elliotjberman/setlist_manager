#!/bin/zsh
set -e

cd "$(dirname "$0")/.."

echo "Starting Ableton Set Manager..."

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing shared dependencies..."
python -m pip install -r requirements.txt

echo "Starting server..."
python server.py
