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
echo "1. Start Keycloak: docker-compose up -d"
echo "2. Wait for Keycloak to be ready: docker-compose logs -f keycloak"
echo "3. Run the server: uv run main.py"
