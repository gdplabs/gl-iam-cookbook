#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies and configures environment

set -e

echo "=========================================="
echo "GL-IAM RBAC Showcase - Setup"
echo "=========================================="
echo ""

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
echo "1. Choose your provider by setting PROVIDER_TYPE in .env:"
echo "   - keycloak (default) - uses local Docker Keycloak"
echo "   - stackauth - requires external Stack Auth instance"
echo ""
echo "2. For Keycloak provider:"
echo "   a. Start Keycloak: docker-compose up -d"
echo "   b. Wait for Keycloak to be ready: docker-compose logs -f keycloak"
echo "   c. Run the server: uv run main.py"
echo ""
echo "3. For Stack Auth provider:"
echo "   a. Configure your Stack Auth credentials in .env"
echo "   b. Run the server: uv run main.py"
echo ""
echo "4. Open API docs: http://localhost:8000/docs"
echo ""
