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
echo 1. Run the permission console (no database required):
echo    uv run main.py
echo.
echo 2. Open http://localhost:8000
