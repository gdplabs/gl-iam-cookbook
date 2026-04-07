# Agent IAM — Real Case Simulation

Interactive web dashboard demonstrating GL-IAM's AI Agent Identity and Access Management.

## Quick Start

```bash
# First time only
make setup

# Run everything (opens 4 terminal windows on macOS)
make run
```

That's it. Open http://localhost:5173 and click **Initialize Demo**.

## What `make run` does

1. Starts PostgreSQL (Docker)
2. Opens 4 Terminal windows:
   - 🔵 GLChat BE (`:8000`) — user auth, ABAC, delegation
   - 🟣 AIP Backend (`:8001`) — tool planning, worker delegation
   - 🟢 GL Connectors (`:8002`) — tool execution
   - 🌐 Dashboard (`:5173`) — React UI

## Commands

| Command | What it does |
|---------|-------------|
| `make setup` | Install Python + Node dependencies (first time) |
| `make run` | Start everything (DB + 4 services in separate terminals) |
| `make stop` | Stop all backend services |
| `make reset-db` | Drop and recreate the database |
| `make health` | Check if all services are running |
| `make clean` | Stop everything + remove DB container |

## Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Node.js 22+ with npm
- Docker (for PostgreSQL)

## Using the Dashboard

1. Click **Initialize Demo** — registers 4 users + 9 agents
2. Pick **Agent** → **User** → **Action**
3. Click **Run Scenario**
4. Explore: Chat Simulation, Delegation Flow, Scope Attenuation, Enforcement Logic, Policy Decision Trace, Audit Trail

### Users

| Name | Role | Org | Access |
|------|------|-----|--------|
| Pak On | Admin | Cross-Org | Full access, wildcard constraints |
| Maylina | Member | GLC | GLC org + Pak On calendar |
| Petry | Member | GLAIR | GLAIR org + Pak On calendar |
| Guest | Viewer | No Org | Pak On calendar only (read) |

### Key Concepts Demonstrated

- **Scope = Tool Name** — google_calendar_events_list, directory_lookup, etc.
- **Resource Constraints** — target_whitelist, write_whitelist in DelegationToken
- **Credential Routing** — User OAuth vs Agent OAuth (deterministic per role)
- **Feature Gates** — invoice_send requires feature entitlement
- **Self-Access** — target == user_email → always allowed, User OAuth
- **Org Boundary** — org:{user.tenant} pattern matches same-org colleagues
- **Audit Trail** — GL-IAM SDK auto-emits login, delegation, agent events
