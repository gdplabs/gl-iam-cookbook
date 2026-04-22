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
echo "1. Stop ldap-keycloak if it's running:  docker-compose -f ../ldap-keycloak/docker-compose.yml down"
echo "2. Start services:                      docker-compose up -d"
echo "3. Wait for Samba + Keycloak to be ready (~90s)"
echo "4. Run the server:                      uv run main.py"
echo ""
echo "AD users (seeded by the ad-init sidecar):"
echo "  - jdoe / jdoe123 (member)"
echo "  - asmith / asmith123 (admin)"
