@echo off
setlocal
cd /D "%~dp0"

where uv >NUL 2>NUL
IF ERRORLEVEL 1 (
    echo ERROR: uv is required. Install it from https://docs.astral.sh/uv/
    EXIT /B 1
)

IF NOT EXIST .env (
    copy /Y .env.example .env >NUL
    echo Created .env from template.
) ELSE (
    echo .env already exists, preserving existing settings.
)

uv sync
IF ERRORLEVEL 1 EXIT /B 1

uv run python -c "from pathlib import Path; from cryptography.fernet import Fernet; p=Path('.env'); s=p.read_text(); marker='GLCHAT_ENCRYPTION_KEY='; lines=s.splitlines(); changed=any(line==marker for line in lines); lines=[marker+Fernet.generate_key().decode() if line==marker else line for line in lines]; p.write_text('\n'.join(lines)+'\n') if changed else None; print('Generated GLCHAT_ENCRYPTION_KEY.' if changed else 'GLCHAT_ENCRYPTION_KEY already configured, preserving it.')"
IF ERRORLEVEL 1 EXIT /B 1

echo.
echo Setup complete. Next steps:
echo   1. docker compose up -d
echo   2. set PYTHONPATH=.
echo   3. uv run python scripts\bootstrap_admin.py
echo   4. Start the services described in README.md

endlocal
