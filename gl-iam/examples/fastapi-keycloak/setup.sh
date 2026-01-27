#!/bin/bash

# Setup script for Unix-based systems
# This script sets up UV authentication and installs dependencies

echo "Setting up UV authentication..."
export UV_INDEX_GEN_AI_INTERNAL_USERNAME=oauth2accesstoken
export UV_INDEX_GEN_AI_INTERNAL_PASSWORD="$(gcloud auth print-access-token)"

echo "Installing dependencies via UV..."
uv lock
uv sync

echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure your settings"
echo "2. Start Keycloak: docker-compose up -d"
echo "3. Wait for Keycloak to be ready: docker-compose logs -f keycloak"
echo "4. Run the server: uv run main.py"
