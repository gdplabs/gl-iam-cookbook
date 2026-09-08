@echo off
setlocal
cd /D "%~dp0"

where uv >NUL 2>NUL
IF ERRORLEVEL 1 (
    echo ERROR: uv is required. Install it from https://docs.astral.sh/uv/
    EXIT /B 1
)

echo Installing dependencies via UV...
uv sync
IF ERRORLEVEL 1 EXIT /B 1

IF NOT EXIST .env (
    echo Creating .env from .env.example...
    copy /Y .env.example .env >NUL
) ELSE (
    echo .env already exists, preserving existing settings...
)

echo.
echo Setup completed successfully!
echo Next steps:
echo   1. Start PostgreSQL as described in README.md
echo   2. Start glchat_be.py, aip_backend.py, and connectors.py in separate terminals
echo   3. Use Git Bash or WSL to run demo.sh, or follow the manual HTTP steps

endlocal
