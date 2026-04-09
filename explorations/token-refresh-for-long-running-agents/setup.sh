#!/bin/bash

# Setup script for Unix-based systems (macOS, Linux)
# This script installs dependencies using UV package manager

set -e

echo "============================================"
echo "TokenManager Exploration - Setup"
echo "============================================"
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "Error: UV package manager is not installed."
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

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
echo "============================================"
echo "Setup completed successfully!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Configure your settings in .env"
echo ""
echo "2. Run the demos:"
echo "   - Simple on-demand refresh:"
echo "     uv run python simple_demo.py"
echo ""
echo "   - Background refresh pattern:"
echo "     uv run python background_demo.py"
echo ""
echo "   - Full deep research agent simulation:"
echo "     uv run python deep_research_agent.py"
echo ""
