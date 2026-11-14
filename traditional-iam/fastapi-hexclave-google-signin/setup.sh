#!/bin/bash
# Installs the FastAPI backend (uv) and the Next.js web app (npm), and creates .env.
set -e

uv sync
(cd web && npm install)
[ -f .env ] || cp .env.example .env

echo ""
echo "Done. Next:"
echo "1. Put your Hexclave project ID and publishable key in .env"
echo "2. Terminal 1: uv run main.py"
echo "3. Terminal 2: cd web && npm run dev"
echo "4. Open http://localhost:3000/"
