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
echo "2. Start PostgreSQL: docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=aip -p 5432:5432 postgres:15"
echo "3. Run the server: uv run main.py"
