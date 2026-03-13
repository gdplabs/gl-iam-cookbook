.PHONY: setup start stop demo logs clean start-services stop-services interactive decode

# ============================================================================
# Setup
# ============================================================================

setup: ## Install dependencies and create .env
	uv sync
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	else \
		echo ".env already exists, skipping..."; \
	fi

# ============================================================================
# PostgreSQL
# ============================================================================

start-db: ## Start PostgreSQL container
	@docker rm -f postgres 2>/dev/null || true
	docker run -d --name postgres \
		-e POSTGRES_PASSWORD=postgres \
		-e POSTGRES_DB=gliam \
		-p 5432:5432 postgres:15
	@echo "Waiting for PostgreSQL..."
	@sleep 3
	@echo "PostgreSQL ready on port 5432"

stop-db: ## Stop PostgreSQL container
	docker rm -f postgres 2>/dev/null || true
	@echo "PostgreSQL stopped"

# ============================================================================
# Services
# ============================================================================

start-services: ## Start services in iTerm2 split panes (or Terminal.app)
	@bash start-services.sh

stop-services: stop ## Alias: stop all services

interactive: start-db start-services demo ## Full interactive: DB + iTerm2 panes + interactive demo

start: ## Start all 3 services in background (headless)
	@echo "Starting GL Connectors (port 8002)..."
	@uv run python connectors.py > /tmp/connectors.log 2>&1 & echo $$! > /tmp/connectors.pid
	@echo "Starting AIP Backend (port 8001)..."
	@uv run python aip_backend.py > /tmp/aip_backend.log 2>&1 & echo $$! > /tmp/aip_backend.pid
	@echo "Starting GLChat BE (port 8000)..."
	@uv run python glchat_be.py > /tmp/glchat_be.log 2>&1 & echo $$! > /tmp/glchat_be.pid
	@sleep 3
	@echo ""
	@echo "Health checks:"
	@curl -sf http://localhost:8000/health && echo "" || echo "  glchat_be (8000): FAILED"
	@curl -sf http://localhost:8001/health && echo "" || echo "  aip_backend (8001): FAILED"
	@curl -sf http://localhost:8002/health && echo "" || echo "  connectors (8002): FAILED"
	@echo ""
	@echo "All services started. Run 'make demo' to execute the E2E demo."

stop: ## Stop all 3 services
	@echo "Stopping services..."
	@pkill -f "python connectors.py" 2>/dev/null || true
	@pkill -f "python aip_backend.py" 2>/dev/null || true
	@pkill -f "python glchat_be.py" 2>/dev/null || true
	@rm -f /tmp/connectors.pid /tmp/aip_backend.pid /tmp/glchat_be.pid
	@echo "All services stopped."

restart: stop start ## Restart all services

# ============================================================================
# Demo
# ============================================================================

demo: ## Run the E2E demo script (services must be running)
	@bash demo.sh

start-demo: start-db start demo ## Full sequence: start DB + services + run demo

stop-demo: stop stop-db ## Stop services + DB

# ============================================================================
# Logs
# ============================================================================

logs: ## Tail all service logs
	@echo "=== GLChat BE (8000) ===" && tail -20 /tmp/glchat_be.log 2>/dev/null && echo ""
	@echo "=== AIP Backend (8001) ===" && tail -20 /tmp/aip_backend.log 2>/dev/null && echo ""
	@echo "=== Connectors (8002) ===" && tail -20 /tmp/connectors.log 2>/dev/null

logs-glchat: ## Tail GLChat BE logs
	@tail -f /tmp/glchat_be.log

logs-aip: ## Tail AIP Backend logs
	@tail -f /tmp/aip_backend.log

logs-connectors: ## Tail Connectors logs
	@tail -f /tmp/connectors.log

# ============================================================================
# Token Inspection
# ============================================================================

decode: ## Decode a DelegationToken JWT: make decode TOKEN=<jwt>
	@uv run python decode_token.py "$(TOKEN)"

# ============================================================================
# Cleanup
# ============================================================================

clean: stop ## Stop services and remove generated files
	@rm -rf .venv uv.lock __pycache__ /tmp/connectors.log /tmp/aip_backend.log /tmp/glchat_be.log
	@echo "Cleaned up."

# ============================================================================
# Help
# ============================================================================

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
