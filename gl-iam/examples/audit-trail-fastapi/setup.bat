@echo off
REM Setup script for Windows systems

echo Installing dependencies via UV...
uv sync

IF NOT EXIST .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo Created .env file. You can customize it if needed.
) ELSE (
    echo .env file already exists, skipping...
)

echo.
echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Start PostgreSQL (if not running):
echo    docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15
echo.
echo 2. Run the server:
echo    uv run main.py
