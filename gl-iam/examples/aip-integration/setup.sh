#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies using UV

echo "Installing dependencies via UV..."
uv sync

echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure your settings"
echo "2. Start PostgreSQL: docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15"
echo "3. Run the server: uv run main.py"
