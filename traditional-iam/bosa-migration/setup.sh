#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies and configures environment

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
echo "1. Generate encryption key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
echo "2. Update ENCRYPTION_KEY in .env with the generated key"
echo "3. Start PostgreSQL: docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15"
echo "4. Run the server: uv run main.py"
echo "5. Open http://localhost:8000/docs to explore the API"
