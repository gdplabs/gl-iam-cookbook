@echo off
echo Installing dependencies via UV...
uv sync

if not exist .env (
    copy .env.example .env
    echo Created .env from .env.example
)

echo.
echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Start services:  docker-compose up -d
echo 2. Wait for both Keycloak instances to be ready (~45s)
echo 3. Run the server:  uv run main.py
