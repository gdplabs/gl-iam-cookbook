#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies using UV

echo "Installing dependencies via UV..."
uv sync

echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure your Stack Auth settings"
echo "2. Ensure Stack Auth is running (cloud or self-hosted)"
echo "3. Run the server: uv run main.py"
