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
