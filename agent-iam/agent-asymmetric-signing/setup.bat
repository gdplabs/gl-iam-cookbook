@echo off
REM Setup script for Windows
REM This script installs dependencies, generates the key pair, and configures the environment

echo Installing dependencies via UV...
call uv sync
if errorlevel 1 exit /b 1

if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
) else (
    echo .env file already exists, skipping...
)

if not exist keys\issuer_private.pem (
    echo Generating the issuer key pair...
    call uv run generate_keys.py
) else (
    echo Key pair already exists, skipping...
)

echo.
echo Setup completed successfully!
echo.
echo Next steps (two terminals, no database required^):
echo 1. Start the issuer:   uv run issuer.py     # http://localhost:8000
echo 2. Start the verifier: uv run verifier.py   # http://localhost:8001
