@echo off

REM Setup script for Windows systems
REM This script installs dependencies and configures environment

echo Installing dependencies via UV...
uv sync

if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
) else (
    echo .env file already exists, skipping...
)

echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Configure your Stack Auth settings in .env
echo 2. Enable Google sign-in in the Stack Auth dashboard (Auth Methods - Google)
echo 3. Run the server: uv run main.py
echo 4. Open http://localhost:8000/ and click 'Sign in with Google'
