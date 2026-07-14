#!/bin/bash
set -e

# GL-IAM is published to GDP Labs' internal Artifact Registry, so uv needs a
# short-lived OAuth token to resolve it. uv derives these variable names from the
# index named "gen-ai-internal" in pyproject.toml.
if ! command -v gcloud >/dev/null 2>&1; then
    echo "ERROR: gcloud CLI not found, but GL-IAM is published to an internal registry."
    echo "Install the Google Cloud SDK (https://cloud.google.com/sdk/docs/install), then:"
    echo "  gcloud auth login"
    exit 1
fi

echo "Authenticating to the gen-ai-internal registry..."
UV_INDEX_GEN_AI_INTERNAL_USERNAME=oauth2accesstoken
UV_INDEX_GEN_AI_INTERNAL_PASSWORD="$(gcloud auth print-access-token)"
export UV_INDEX_GEN_AI_INTERNAL_USERNAME UV_INDEX_GEN_AI_INTERNAL_PASSWORD

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
