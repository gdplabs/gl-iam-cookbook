#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies and configures environment

set -e
echo "Installing dependencies via UV..."
uv sync

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Created .env file. You can customize it if needed."
else
    echo ".env file already exists, skipping..."
fi

echo ""
echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Run the permission console (no database required):"
echo "   uv run main.py"
echo ""
echo "2. Open http://localhost:8000"
