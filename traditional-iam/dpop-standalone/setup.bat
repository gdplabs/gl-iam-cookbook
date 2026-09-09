@echo off
setlocal

echo Setting up DPoP Standalone (no Keycloak) example...
where uv >NUL 2>NUL
IF ERRORLEVEL 1 (
    echo ERROR: uv is required. Install it from https://docs.astral.sh/uv/
    EXIT /B 1
)

IF NOT EXIST .env (
    copy /Y .env.example .env >NUL
    echo Created .env from .env.example
) ELSE (
    echo .env already exists, skipping...
)

echo Installing dependencies...
uv sync
IF ERRORLEVEL 1 EXIT /B 1

echo.
echo Setup complete! No Keycloak, no database required.
echo Next steps:
echo   1. Generate a client key:  uv run generate_key.py
echo   2. Mint a bound token:     uv run issue_token.py
echo   3. Run the resource server: uv run main.py
echo   4. Generate a proof:       uv run create_proof.py GET http://localhost:8000/api/protected "^<token^>"

endlocal
