#!/bin/bash
set -e

echo "Setting up DPoP Standalone (no Keycloak) example..."

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
echo "Setup complete! No Keycloak, no database required."
echo ""
echo "Next steps:"
echo "  1. Generate a client key:  uv run generate_key.py"
echo "  2. Mint a bound token:     uv run issue_token.py"
echo "  3. Run the resource server: uv run main.py"
echo "  4. Generate a proof:       uv run create_proof.py GET http://localhost:8000/api/protected \"<token>\""
echo "  5. Call the protected API with the token + proof (see README)"
