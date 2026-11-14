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
echo 2. Terminal 1: uv run main.py
echo 3. Terminal 2: cd web, then npm run dev
echo 4. Open http://localhost:3000/
