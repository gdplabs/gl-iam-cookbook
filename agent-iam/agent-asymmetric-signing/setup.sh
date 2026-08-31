#!/bin/bash

# Setup script for Unix-based systems
# This script installs dependencies, generates the key pair, and configures the environment

set -e
echo "Installing dependencies via UV..."
uv sync

if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
else
    echo ".env file already exists, skipping..."
fi

if [ ! -f keys/issuer_private.pem ]; then
    echo "Generating the issuer key pair..."
    uv run generate_keys.py
else
    echo "Key pair already exists, skipping..."
fi

echo ""
echo "Setup completed successfully!"
echo ""
echo "Next steps (two terminals, no database required):"
echo "1. Start the issuer:   uv run issuer.py     # http://localhost:8000"
echo "2. Start the verifier: uv run verifier.py   # http://localhost:8001"
