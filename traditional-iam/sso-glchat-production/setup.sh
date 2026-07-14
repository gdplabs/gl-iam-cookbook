#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from template."
fi

# Generate Fernet key if missing (line is "GLCHAT_ENCRYPTION_KEY=" with nothing after)
if grep -qE "^GLCHAT_ENCRYPTION_KEY=\s*$" .env; then
  KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|^GLCHAT_ENCRYPTION_KEY=.*|GLCHAT_ENCRYPTION_KEY=$KEY|" .env
  else
    sed -i "s|^GLCHAT_ENCRYPTION_KEY=.*|GLCHAT_ENCRYPTION_KEY=$KEY|" .env
  fi
  echo "Generated GLCHAT_ENCRYPTION_KEY."
fi

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
echo "Setup complete. Next steps:"
echo "  1. make up          # start Postgres + Redis"
echo "  2. make bootstrap   # create admin + register partner"
echo "  3. make run-all     # start backends + static file server"
echo "  4. make demo        # run scripted end-to-end test"
