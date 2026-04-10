#!/bin/bash
set -e

echo "Installing dependencies via UV..."
uv sync

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

echo ""
echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Start services:  docker-compose up -d"
echo "2. Wait for Keycloak to be ready (~30s)"
echo "3. Run the server:  uv run main.py"
echo ""
echo "LDAP users (from OpenLDAP):"
echo "  - jdoe / jdoe123 (member)"
echo "  - asmith / asmith123 (admin)"
