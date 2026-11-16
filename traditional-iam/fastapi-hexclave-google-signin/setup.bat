@echo off
REM Installs the FastAPI backend (uv) and the Next.js web app (npm), and creates .env.

call uv sync
pushd web
call npm install
popd
if not exist .env copy .env.example .env

echo.
echo Done. Next:
echo 1. Put your Hexclave project ID and publishable key in .env
echo 2. Run both: npx --yes concurrently@9.2.5 "uv run main.py" "npm --prefix web run dev"
echo 3. Open http://localhost:3000/
