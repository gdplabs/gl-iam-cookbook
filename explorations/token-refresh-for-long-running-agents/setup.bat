@echo off
REM Setup script for Windows systems
REM This script installs dependencies using UV package manager

echo ============================================
echo TokenManager Exploration - Setup
echo ============================================
echo.

REM Check if UV is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: UV package manager is not installed.
    echo Install it from: https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)

echo Installing dependencies via UV...
uv sync

if %ERRORLEVEL% equ 0 (
    echo.
    echo ============================================
    echo Setup completed successfully!
    echo ============================================
    echo.
    echo Next steps:
    echo 1. Copy .env.example to .env and configure settings:
    echo    copy .env.example .env
    echo.
    echo 2. Run the demos:
    echo    - Simple on-demand refresh:
    echo      uv run python simple_demo.py
    echo.
    echo    - Background refresh pattern:
    echo      uv run python background_demo.py
    echo.
    echo    - Full deep research agent simulation:
    echo      uv run python deep_research_agent.py
    echo.
) else (
    echo.
    echo Error: Setup failed. Please check the error messages above.
    exit /b 1
)
