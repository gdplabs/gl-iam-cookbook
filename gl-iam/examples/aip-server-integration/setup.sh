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
echo "1. Start PostgreSQL: docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=aip -p 5432:5432 postgres:15"
echo "2. Run the server: uv run main.py"
