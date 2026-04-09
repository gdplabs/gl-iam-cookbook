@echo off
REM Setup script for Windows systems
REM This script installs dependencies using UV

echo ==========================================
echo GL-IAM RBAC Showcase - Setup
echo ==========================================
echo.

echo Installing dependencies via UV...
uv sync

echo.
echo Setup completed successfully!
echo.
echo Next steps:
echo 1. Copy .env.example to .env:
echo    copy .env.example .env
echo.
echo 2. Choose your provider by setting PROVIDER_TYPE in .env:
echo    - keycloak (default) - uses local Docker Keycloak
echo    - stackauth - requires external Stack Auth instance
echo.
echo 3. For Keycloak provider:
echo    a. Start Keycloak: docker-compose up -d
echo    b. Wait for Keycloak to be ready: docker-compose logs -f keycloak
echo    c. Run the server: uv run main.py
echo.
echo 4. For Stack Auth provider:
echo    a. Configure your Stack Auth credentials in .env
echo    b. Run the server: uv run main.py
echo.
echo 5. Open API docs: http://localhost:8000/docs
echo.
