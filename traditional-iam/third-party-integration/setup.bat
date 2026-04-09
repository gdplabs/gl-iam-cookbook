@echo off
REM Setup script for Windows systems
REM This script installs dependencies and configures environment

echo Installing dependencies via UV...
uv sync

REM Copy .env.example to .env if it doesn't exist
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo Created .env file. Please configure your GitHub OAuth credentials.
    echo.
    echo To generate an encryption key, run:
    echo   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    echo Then update ENCRYPTION_KEY in your .env file.
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
echo 2. Create a GitHub OAuth App at https://github.com/settings/developers
echo    - Authorization callback URL: http://localhost:8000/connectors/github/callback
echo.
echo 3. Update .env with your GitHub OAuth credentials
echo.
echo 4. Run the server:
echo    uv run main.py
