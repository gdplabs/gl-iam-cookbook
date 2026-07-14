#!/bin/bash
set -e

echo "=== Agent IAM Delegation E2E Demo Setup ==="
echo ""

# Install dependencies
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

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Created .env file. You can customize it if needed."
else
    echo ".env file already exists, skipping..."
fi

echo ""
echo "Setup completed!"
echo ""
echo "Next steps:"
echo ""
echo "1. Start PostgreSQL (if not running):"
echo "   docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15"
echo ""
echo "2. Start all 3 services in separate terminals:"
echo "   Terminal 1: uv run glchat_be.py     # port 8000"
echo "   Terminal 2: uv run aip_backend.py   # port 8001"
echo "   Terminal 3: uv run connectors.py    # port 8002"
echo ""
echo "3. Run the demo:"
echo "   ./demo.sh"
