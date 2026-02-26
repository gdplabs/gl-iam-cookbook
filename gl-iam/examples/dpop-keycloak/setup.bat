@echo off
REM Setup script for Windows

echo Setting up DPoP Keycloak example...

REM Copy .env.example to .env if it doesn't exist
if not exist .env (
    copy .env.example .env
    echo Created .env from .env.example
)

REM Sync dependencies
echo Installing dependencies...
call uv sync

echo.
echo Setup complete!
echo.
echo Next steps:
echo   1. Start Keycloak: docker-compose up -d
echo   2. Run server:     uv run main.py
echo " 3. Generate key:   uv run generate_key.py"
echo " 4. Generate proof: uv run craetea_proof.py"
