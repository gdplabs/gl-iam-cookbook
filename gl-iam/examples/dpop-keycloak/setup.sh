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
uv sync

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start Keycloak: docker-compose up -d"
echo "  2. Run server:     uv run main.py"
echo "  3. Generate key:   uv run generate_key.py"
echo "  4. Generate proof: uv run craetea_proof.py"
