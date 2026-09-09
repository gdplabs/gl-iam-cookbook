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
    echo .env already exists, preserving existing settings...
)

REM Replace only the committed placeholder. Existing user-managed keys remain intact.
uv run python -c "from pathlib import Path; from cryptography.fernet import Fernet; p=Path('.env'); s=p.read_text(); marker='ENCRYPTION_KEY=your-fernet-encryption-key-here'; changed=marker in s; p.write_text(s.replace(marker, 'ENCRYPTION_KEY='+Fernet.generate_key().decode(), 1)) if changed else None; print('Generated ENCRYPTION_KEY.' if changed else 'ENCRYPTION_KEY already configured, preserving it.')"
IF ERRORLEVEL 1 EXIT /B 1

echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Review .env and configure your settings if needed
echo 2. Start PostgreSQL: docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=gliam -p 5432:5432 postgres:15
echo 3. Run the server: uv run main.py
echo 4. Open http://localhost:8000/docs to explore the API
