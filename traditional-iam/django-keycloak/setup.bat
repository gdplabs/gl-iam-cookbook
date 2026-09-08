@echo off

REM Setup script for Windows systems
REM This script installs dependencies using UV

echo Installing dependencies via UV...
uv sync
IF ERRORLEVEL 1 EXIT /B 1

IF NOT EXIST .env (
    echo Creating .env from .env.example...
    copy /Y .env.example .env >NUL
) ELSE (
    echo .env already exists, skipping...
)

echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Review .env and configure your settings if needed
echo 2. Start Keycloak: docker-compose up -d
echo 3. Run the server: uv run python manage.py runserver
