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
echo 1. Stop ldap-keycloak if running:  docker-compose -f ..\ldap-keycloak\docker-compose.yml down
echo 2. Start services:                  docker-compose up -d
echo 3. Wait for Samba + Keycloak ready (~90s)
echo 4. Run the server:                  uv run main.py
