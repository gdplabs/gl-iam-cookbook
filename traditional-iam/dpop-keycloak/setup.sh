#!/bin/bash
set -e

echo "Setting up DPoP Keycloak example..."

# Install uv if not present
if ! command -v uv &>/dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

# Sync dependencies
echo "Installing dependencies..."
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

uv sync

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start Keycloak: docker-compose up -d"
echo "  2. Run server:     uv run main.py"
echo "  3. Generate key:   uv run generate_key.py"
echo "  4. Generate proof: uv run create_proof.py ..."
