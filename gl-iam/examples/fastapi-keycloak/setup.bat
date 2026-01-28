@echo off

REM Setup script for Windows systems
REM This script installs dependencies using UV

echo Installing dependencies via UV...
uv sync

echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Copy .env.example to .env and configure your settings
echo 2. Start Keycloak: docker-compose up -d
echo 3. Wait for Keycloak to be ready: docker-compose logs -f keycloak
echo 4. Run the server: uv run main.py
