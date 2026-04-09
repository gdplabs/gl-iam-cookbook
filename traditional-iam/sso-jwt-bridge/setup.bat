@echo off

REM Setup script for Windows systems
REM This script installs dependencies and configures environment

echo Installing dependencies via UV...
uv sync

REM Copy .env.example to .env if it doesn't exist
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo Created .env file. You can customize it if needed.
) else (
    echo .env file already exists, skipping...
)

echo.
echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Start PostgreSQL (if not running):
echo    docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15
echo.
echo 2. Run the SSO receiver:
echo    uv run sso_receiver.py
echo.
echo 3. In another terminal, run the partner client:
echo    uv run partner_client.py
