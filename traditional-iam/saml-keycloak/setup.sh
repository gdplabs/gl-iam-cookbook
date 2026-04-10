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
echo "2. Wait for both Keycloak instances to be ready (~45s)"
echo "3. Run the server:  uv run main.py"
echo ""
echo "SAML IdP users (simulated corporate users):"
echo "  - alice@corporate.com / alice123 (employee)"
echo "  - bob@corporate.com / bob123 (manager)"
echo ""
echo "SAML flow: Browser → Keycloak SP → SAML IdP → authenticate → back to SP → OIDC token"
