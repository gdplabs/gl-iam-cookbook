.PHONY: help quickstart interactive setup up down install bootstrap run-glchat run-partner run-fe run-all stop logs demo clean

PY := PYTHONPATH=. uv run

help:
	@echo "Targets:"
	@echo "  make interactive    Setup + up + bootstrap + run-all (skips demo, leaves services running for browser use)"
	@echo "  make quickstart     End-to-end: setup + up + bootstrap + run-all + demo"
	@echo "  make setup          Copy .env.example, generate Fernet key, uv sync"
	@echo "  make up             Start Postgres (host :55432) + Redis (host :56379)"
	@echo "  make down           Stop Postgres + Redis"
	@echo "  make bootstrap      Create platform admin + register partner"
	@echo "  make run-all        Launch GLChat BE, Partner BE, static frontends (bg)"
	@echo "  make stop           Kill the 3 background backends"
	@echo "  make logs           tail -f /tmp/sso-glchat-*.log"
	@echo "  make demo           Run scripts/demo_e2e.py (all gap assertions)"
	@echo "  make clean          Stop everything and remove logs"

quickstart: setup up wait-db bootstrap run-all wait-be demo
	@echo ""
	@echo "======================================================================"
	@echo " Quickstart complete."
	@echo ""
	@echo " Browse:"
	@echo "   http://localhost:3001  Partner site"
	@echo "                          login: alice@trusted-partner.example.com / alice-pass"
	@echo "   http://localhost:3002  Admin dashboard"
	@echo "                          login: admin@glchat.example.com / AdminPass123!"
	@echo ""
	@echo " NOTE: the rate limiter is saturated for ~60s right after the demo."
	@echo "       If the partner-site 'Open GLChat' button returns 429, either:"
	@echo "         - wait 60 seconds and retry, OR"
	@echo "         - 'make stop && make run-all' to reset the in-process limiter."
	@echo ""
	@echo " Stop with:  make stop && make down"
	@echo "======================================================================"

# Exactly like quickstart but without the demo so the partner's consumer_secret
# and the rate-limit window remain pristine for a human browser walkthrough.
interactive: setup up wait-db bootstrap run-all wait-be
	@echo ""
	@echo "======================================================================"
	@echo " Services are up. Ready for an interactive browser demo."
	@echo ""
	@echo "   http://localhost:3001  Partner site"
	@echo "                          login: alice@trusted-partner.example.com / alice-pass"
	@echo "                          (also: bob@trusted-partner.example.com / bob-pass)"
	@echo "   http://localhost:3002  Admin dashboard"
	@echo "                          login: admin@glchat.example.com / AdminPass123!"
	@echo "   http://localhost:3003  Widget origin (loaded as iframe, not browsed directly)"
	@echo ""
	@echo " Walkthrough:"
	@echo "   1. Open http://localhost:3001"
	@echo "   2. Click 'Log in' (pre-filled alice credentials)"
	@echo "   3. Click 'Open GLChat' -- widget loads in iframe and auto-authenticates"
	@echo "   4. Open http://localhost:3002 to see the partner + audit trail"
	@echo ""
	@echo " Stop with:  make stop && make down"
	@echo "======================================================================"

setup:
	./setup.sh

up:
	docker compose up -d

wait-db:
	@echo "Waiting for Postgres on :55432..."
	@for i in $$(seq 1 30); do \
	  docker exec sso-glchat-postgres pg_isready -U postgres >/dev/null 2>&1 && break; \
	  sleep 1; \
	done
	@echo "Postgres ready."

down:
	docker compose down

install:
	uv sync

bootstrap:
	$(PY) python scripts/bootstrap_admin.py
	$(PY) python -m glchat_backend.main > /tmp/sso-glchat-bootstrap-be.log 2>&1 & \
	  BE_PID=$$!; \
	  for i in $$(seq 1 20); do curl -sf http://localhost:8000/health >/dev/null && break; sleep 1; done; \
	  $(PY) python scripts/bootstrap_partner.py; \
	  kill $$BE_PID 2>/dev/null || true; \
	  wait $$BE_PID 2>/dev/null || true

run-glchat:
	$(PY) python -m glchat_backend.main

run-partner:
	$(PY) python -m partner_backend.main

run-fe:
	$(PY) python scripts/serve_frontends.py

run-all: stop
	@mkdir -p /tmp
	@$(PY) python -m glchat_backend.main > /tmp/sso-glchat-be.log 2>&1 &
	@$(PY) python -m partner_backend.main > /tmp/sso-glchat-partner.log 2>&1 &
	@$(PY) python scripts/serve_frontends.py > /tmp/sso-glchat-fe.log 2>&1 &
	@echo "Launched backends + FE in background."
	@echo "  GLChat BE:     http://localhost:8000"
	@echo "  Partner BE:    http://localhost:8001"
	@echo "  Partner site:  http://localhost:3001"
	@echo "  Admin UI:      http://localhost:3002"
	@echo "  GLChat widget: http://localhost:3003"
	@echo "  Tail logs:     make logs"
	@echo "  Stop all:      make stop"

wait-be:
	@echo "Waiting for GLChat BE on :8000..."
	@for i in $$(seq 1 30); do curl -sf http://localhost:8000/health >/dev/null && break; sleep 1; done
	@echo "Waiting for Partner BE on :8001..."
	@for i in $$(seq 1 30); do curl -sf http://localhost:8001/health >/dev/null && break; sleep 1; done

stop:
	-@pkill -f "glchat_backend.main" 2>/dev/null || true
	-@pkill -f "partner_backend.main" 2>/dev/null || true
	-@pkill -f "scripts/serve_frontends.py" 2>/dev/null || true
	-@sleep 1

logs:
	tail -f /tmp/sso-glchat-*.log

demo:
	$(PY) python scripts/demo_e2e.py

clean: stop down
	rm -f /tmp/sso-glchat-*.log
