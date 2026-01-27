@echo off

REM Setup script for Windows systems
REM This script sets up UV authentication and installs dependencies

echo Setting up UV authentication...
set UV_INDEX_GEN_AI_INTERNAL_USERNAME=oauth2accesstoken
for /f "delims=" %%i in ('gcloud auth print-access-token') do set UV_INDEX_GEN_AI_INTERNAL_PASSWORD=%%i

echo Installing dependencies via UV...
uv lock
uv sync

REM Install glaip-sdk separately if available
echo Installing glaip-sdk (if available)...
pip install "glaip-sdk[local]" 2>nul || echo Note: glaip-sdk not available, agent features will be simulated

echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Copy .env.example to .env and configure your settings
echo 2. Start PostgreSQL: docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15
echo 3. Run the server: uv run main.py
