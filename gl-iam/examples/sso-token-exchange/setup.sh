#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies and configures environment

set -e

echo "Installing dependencies via UV..."
uv sync

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env

    # Generate a Fernet encryption key
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "your-fernet-encryption-key-here")
    if [ "$FERNET_KEY" != "your-fernet-encryption-key-here" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|your-fernet-encryption-key-here|$FERNET_KEY|" .env
        else
            sed -i "s|your-fernet-encryption-key-here|$FERNET_KEY|" .env
        fi
        echo "Generated Fernet encryption key."
    fi

    echo "Created .env file. You can customize it if needed."
else
    echo ".env file already exists, skipping..."
fi

echo ""
echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Start PostgreSQL (if not running):"
echo "   docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15"
echo ""
echo "2. Run the SSO receiver:"
echo "   uv run sso_receiver.py"
echo ""
echo "3. In another terminal, run the partner client:"
echo "   uv run partner_client.py"
