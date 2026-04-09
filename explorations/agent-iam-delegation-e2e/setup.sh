#!/bin/bash
set -e

echo "=== Agent IAM Delegation E2E Demo Setup ==="
echo ""

# Install dependencies
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
echo "Setup completed!"
echo ""
echo "Next steps:"
echo ""
echo "1. Start PostgreSQL (if not running):"
echo "   docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15"
echo ""
echo "2. Start all 3 services in separate terminals:"
echo "   Terminal 1: uv run glchat_be.py     # port 8000"
echo "   Terminal 2: uv run aip_backend.py   # port 8001"
echo "   Terminal 3: uv run connectors.py    # port 8002"
echo ""
echo "3. Run the demo:"
echo "   ./demo.sh"
