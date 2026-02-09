#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies, configures environment, and generates encryption key

set -e

echo "Installing dependencies via UV..."
uv sync

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env

    # Auto-generate a Fernet encryption key if python3 is available
    if command -v python3 &> /dev/null; then
        echo "Generating Fernet encryption key..."
        FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
        if [ -n "$FERNET_KEY" ]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|ENCRYPTION_KEY=your-fernet-encryption-key-here|ENCRYPTION_KEY=$FERNET_KEY|" .env
            else
                sed -i "s|ENCRYPTION_KEY=your-fernet-encryption-key-here|ENCRYPTION_KEY=$FERNET_KEY|" .env
            fi
            echo "Encryption key generated and saved to .env"
        else
            echo "Warning: Could not generate encryption key (cryptography package not found in system Python)."
            echo "You can generate one after setup: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        fi
    fi

    echo "Created .env file. Please configure your GitHub OAuth credentials."
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
echo "2. Create a GitHub OAuth App:"
echo "   Go to https://github.com/settings/developers"
echo "   - Application name: GL-IAM Demo"
echo "   - Homepage URL: http://localhost:8000"
echo "   - Authorization callback URL: http://localhost:8000/connectors/github/callback"
echo ""
echo "3. Update .env with your GitHub OAuth credentials:"
echo "   GITHUB_CLIENT_ID=your-client-id"
echo "   GITHUB_CLIENT_SECRET=your-client-secret"
echo ""
echo "4. Run the server:"
echo "   uv run main.py"
