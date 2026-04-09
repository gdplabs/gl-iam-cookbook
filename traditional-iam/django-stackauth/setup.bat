@echo off

REM Setup script for Windows systems
REM This script installs dependencies using UV

echo Installing dependencies via UV...
uv sync

echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Copy .env.example to .env and configure your Stack Auth settings
echo 2. Make sure Stack Auth is running (or use the hosted version)
echo 3. Run the server: uv run python manage.py runserver
