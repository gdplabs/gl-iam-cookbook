.PHONY: setup run start stop clean health reset-db

# =============================================================================
# 🚀 One-command setup + run
# =============================================================================

# First time: make setup && make run
# After that: make run

setup:
	@echo "📦 Installing Python dependencies..."
	uv sync
	@test -f .env || cp .env.example .env
	@echo "📦 Installing dashboard dependencies..."
	cd dashboard && npm install
	@echo ""
	@echo "✅ Setup complete! Run: make run"

run: start-db
	@sleep 2
	@echo ""
	@echo "🚀 Launching Agent IAM — Real Case Simulation"
	@echo ""
	@# Detect terminal emulator and launch tabs
	@if [ "$$(uname)" = "Darwin" ]; then \
		$(MAKE) _run-macos; \
	else \
		$(MAKE) _run-linux; \
	fi

# macOS: open 4 Terminal.app tabs
_run-macos:
	@osascript -e ' \
		tell application "Terminal" \
			activate \
			set projectDir to "$(CURDIR)" \
			do script "cd " & projectDir & "/backend && echo \"🔵 GLChat BE (:8000)\" && uv run python glchat_be.py" \
			delay 1 \
			do script "cd " & projectDir & "/backend && echo \"🟣 AIP Backend (:8001)\" && uv run python aip_backend.py" \
			delay 1 \
			do script "cd " & projectDir & "/backend && echo \"🟢 Connectors (:8002)\" && uv run python connectors.py" \
			delay 1 \
			do script "cd " & projectDir & "/dashboard && echo \"🌐 Dashboard (:5173)\" && npm run dev" \
		end tell \
	' 2>/dev/null || $(MAKE) _run-background
	@echo ""
	@echo "=== 4 Terminal windows opened ==="
	@echo "  🔵 GLChat BE        → http://localhost:8000"
	@echo "  🟣 AIP Backend      → http://localhost:8001"
	@echo "  🟢 GL Connectors    → http://localhost:8002"
	@echo "  🌐 Dashboard        → http://localhost:5173"
	@echo ""
	@echo "Open http://localhost:5173 in your browser"
	@echo "Click 'Initialize Demo' to get started"

# Linux / fallback: run in background
_run-linux:
	@$(MAKE) _run-background

_run-background:
	@echo "Starting services in background..."
	cd backend && uv run python glchat_be.py > /tmp/glchat_be.log 2>&1 &
	@sleep 3
	cd backend && uv run python aip_backend.py > /tmp/aip_backend.log 2>&1 &
	@sleep 2
	cd backend && uv run python connectors.py > /tmp/connectors.log 2>&1 &
	@sleep 2
	@echo ""
	@echo "=== Backend services started ==="
	@echo "  🔵 GLChat BE        → http://localhost:8000"
	@echo "  🟣 AIP Backend      → http://localhost:8001"
	@echo "  🟢 GL Connectors    → http://localhost:8002"
	@echo ""
	@echo "Starting dashboard..."
	cd dashboard && npm run dev

# =============================================================================
# Database
# =============================================================================

start-db:
	@echo "🐘 Starting PostgreSQL..."
	@if docker ps --format '{{.Names}}' | grep -q gliam-dashboard-db; then \
		echo "  gliam-dashboard-db already running."; \
	elif docker start gliam-dashboard-db 2>/dev/null; then \
		echo "  Started existing gliam-dashboard-db container."; \
	elif docker ps --format '{{.Ports}}' | grep -q '5432->5432'; then \
		echo "  Port 5432 in use. Reusing existing PostgreSQL."; \
		docker exec $$(docker ps --filter "publish=5432" --format '{{.Names}}' | head -1) \
			psql -U postgres -c "CREATE DATABASE gliam_dashboard;" 2>/dev/null || true; \
	else \
		docker run -d --name gliam-dashboard-db \
			-e POSTGRES_PASSWORD=postgres \
			-e POSTGRES_DB=gliam_dashboard \
			-p 5432:5432 \
			postgres:15; \
		sleep 3; \
	fi
	@echo "  PostgreSQL ready on :5432"

reset-db:
	@echo "🔄 Resetting database..."
	@docker exec $$(docker ps --filter "publish=5432" --format '{{.Names}}' | head -1) \
		psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='gliam_dashboard' AND pid!=pg_backend_pid();" 2>/dev/null || true
	@docker exec $$(docker ps --filter "publish=5432" --format '{{.Names}}' | head -1) \
		psql -U postgres -c "DROP DATABASE IF EXISTS gliam_dashboard;" 2>/dev/null
	@docker exec $$(docker ps --filter "publish=5432" --format '{{.Names}}' | head -1) \
		psql -U postgres -c "CREATE DATABASE gliam_dashboard;" 2>/dev/null
	@echo "  Database reset complete."

# =============================================================================
# Individual commands
# =============================================================================

start: run

stop:
	@echo "Stopping services..."
	@pkill -f "python glchat_be.py" 2>/dev/null || true
	@pkill -f "python aip_backend.py" 2>/dev/null || true
	@pkill -f "python connectors.py" 2>/dev/null || true
	@echo "Services stopped."

clean: stop
	@docker stop gliam-dashboard-db 2>/dev/null || true
	@echo "Cleaned up."

health:
	@echo "Health check:"
	@echo "  GLChat BE:   $$(curl -s http://localhost:8000/health 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])' 2>/dev/null || echo 'DOWN')"
	@echo "  AIP Backend: $$(curl -s http://localhost:8001/health 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])' 2>/dev/null || echo 'DOWN')"
	@echo "  Connectors:  $$(curl -s http://localhost:8002/health 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])' 2>/dev/null || echo 'DOWN')"

logs:
	@tail -f /tmp/glchat_be.log /tmp/aip_backend.log /tmp/connectors.log 2>/dev/null || \
		echo "No log files. Services may be running in terminal tabs."
