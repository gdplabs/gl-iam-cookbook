.PHONY: setup setup-backend setup-dashboard start start-db start-services start-dashboard stop clean

# ── Setup ──
setup: setup-backend setup-dashboard

setup-backend:
	@echo "Installing Python dependencies..."
	uv sync
	@test -f .env || cp .env.example .env
	@echo "Backend ready."

setup-dashboard:
	@echo "Installing dashboard dependencies..."
	cd dashboard && npm install
	@echo "Dashboard ready."

# ── Database ──
start-db:
	@echo "Starting PostgreSQL..."
	@if docker ps --format '{{.Names}}' | grep -q gliam-dashboard-db; then \
		echo "gliam-dashboard-db already running."; \
	elif docker start gliam-dashboard-db 2>/dev/null; then \
		echo "Started existing gliam-dashboard-db container."; \
	elif docker ps --format '{{.Ports}}' | grep -q '5432->5432'; then \
		echo "Port 5432 in use by another container. Reusing existing PostgreSQL."; \
		docker exec $$(docker ps --filter "publish=5432" --format '{{.Names}}' | head -1) \
			psql -U postgres -c "CREATE DATABASE gliam_dashboard;" 2>/dev/null || true; \
	else \
		docker run -d --name gliam-dashboard-db \
			-e POSTGRES_PASSWORD=postgres \
			-e POSTGRES_DB=gliam_dashboard \
			-p 5432:5432 \
			postgres:15; \
	fi
	@echo "PostgreSQL ready on :5432"

stop-db:
	@docker stop gliam-dashboard-db 2>/dev/null || true

# ── Backend Services ──
start-services:
	@echo "Starting 3 backend services..."
	cd backend && uv run python glchat_be.py &
	cd backend && uv run python aip_backend.py &
	cd backend && uv run python connectors.py &
	@echo "Services starting on :8000, :8001, :8002"

start-services-fg:
	@echo "Starting services in foreground (use separate terminals)..."
	@echo "Terminal 1: cd backend && uv run python glchat_be.py"
	@echo "Terminal 2: cd backend && uv run python aip_backend.py"
	@echo "Terminal 3: cd backend && uv run python connectors.py"

# ── Dashboard ──
start-dashboard:
	cd dashboard && npm run dev

# ── Full Start ──
start: start-db
	@sleep 2
	@$(MAKE) start-services
	@sleep 3
	@echo ""
	@echo "=== Agent IAM Dashboard ==="
	@echo "Backend:   http://localhost:8000 (GLChat BE)"
	@echo "           http://localhost:8001 (AIP Backend)"
	@echo "           http://localhost:8002 (Connectors)"
	@echo "Dashboard: Run 'make start-dashboard' in another terminal"
	@echo ""

# ── Stop ──
stop:
	@pkill -f "glchat_be.py" 2>/dev/null || true
	@pkill -f "aip_backend.py" 2>/dev/null || true
	@pkill -f "connectors.py" 2>/dev/null || true
	@echo "Services stopped."

clean: stop stop-db
	@echo "Cleaned up."

# ── Logs ──
logs:
	@tail -f /tmp/glchat_be.log /tmp/aip_backend.log /tmp/connectors.log 2>/dev/null || \
		echo "No log files found. Services log to stdout."

# ── Health Check ──
health:
	@echo "GLChat BE:  $$(curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo 'DOWN')"
	@echo "AIP Backend: $$(curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null || echo 'DOWN')"
	@echo "Connectors:  $$(curl -s http://localhost:8002/health | python3 -m json.tool 2>/dev/null || echo 'DOWN')"
