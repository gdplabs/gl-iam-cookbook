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

uv sync
echo ""
echo "Setup complete. Next steps:"
echo "  1. make up          # start Postgres + Redis"
echo "  2. make bootstrap   # create admin + register partner"
echo "  3. make run-all     # start backends + static file server"
echo "  4. make demo        # run scripted end-to-end test"
