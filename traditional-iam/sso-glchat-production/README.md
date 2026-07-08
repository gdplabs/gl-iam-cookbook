# GLChat Production SSO (IdP-Initiated)

A reference cookbook for **production-grade IdP-Initiated SSO** between GLChat and a Trusted Partner, using the [GL-IAM SDK](https://github.com/GDP-ADMIN/gl-sdk) `PartnerRegistryProvider`. Unlike the simpler [`sso-token-exchange`](https://github.com/gdplabs/gl-iam-cookbook/tree/main/traditional-iam/sso-token-exchange) example, this cookbook demonstrates **every** production concern called out in `§12` of the SDK's [IdP-vs-SP Comparison](https://github.com/GDP-ADMIN/gl-sdk/blob/main/libs/gl-iam/docs/architecture/IDP_VS_SP_INITIATED_SSO_COMPARISON.md).

## What this simulates

A real deployment has **five** components across **three trust boundaries**. This cookbook runs all five locally:

```
Partner Site FE (:3001)   ──── GLChat Admin FE (:3002)
        │                              │
        ▼                              ▼
Partner Backend (:8001)        GLChat Backend (:8000)
        │      HMAC-signed            │ ├── PostgreSQL (host :55432 → container 5432)
        └─────────────────────────────┘ ├── Redis      (host :56379 → container 6379)
                                        └── Partner registry, audit log, rate limit, CSP

              ┌── GLChat Widget FE (:3003) — loaded in iframe by Partner Site
```

## Gap-coverage matrix

Every row below is implemented here and asserted by `scripts/demo_e2e.py`.

| # | Production concern | Where implemented |
|---|---|---|
| 1 | **Redis-backed one-time tokens** (atomic `GETDEL`) | `glchat_backend/services/token_store.py` |
| 2 | **Admin endpoint auth** (`require_platform_admin`) | `glchat_backend/routers/admin.py` |
| 3 | **IP allowlist enforcement** (SDK `validate_partner_signature(source_ip=…)`) | `glchat_backend/services/sso_service.py` + `middleware/audit_context.py` |
| 4 | **`max_users` cap enforcement** | `services/sso_service.SSOService._count_partner_users` |
| 5 | **`allowed_roles` enforcement** | `services/sso_service.SSOService.exchange_token` |
| 6 | **Per-`consumer_key` rate limiting** (SlowAPI) | `glchat_backend/middleware/rate_limit.py` |
| 7 | **HMAC nonce replay protection** (Redis `SETNX`) | `glchat_backend/services/nonce_store.py` |
| 8 | **Dynamic `frame-ancestors` CSP** | `glchat_backend/middleware/csp.py` |
| 9 | **`postMessage` token delivery** (never in URL) | `frontends/partner_site/index.html` + `frontends/glchat_widget/index.html` |
| 10 | **Tight timestamp tolerance** (60 s, SDK param) | `glchat_backend/services/sso_service.py` |
| 11 | **Audit logging** (console + Postgres, 9 SSO event tags) | `glchat_backend/audit.py` + `routers/admin.py::get_audit_log` |
| 12 | **Secret rotation with grace period** | admin UI `Rotate (1h grace)` button → `POST /admin/partners/{id}/rotate` |
| 13 | **Real iframe widget** | `frontends/glchat_widget/index.html` |
| 14 | **Partner FE + BE realism** (login → session cookie → SSO bridge) | `frontends/partner_site/` + `partner_backend/` |
| 15 | **Admin FE realism** (partner CRUD, rotate, deactivate, audit viewer) | `frontends/glchat_admin/` |

## Prerequisites

- Docker + Docker Compose
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- `gcloud auth login` (GL-IAM SDK is pulled from `gen-ai-internal` registry for some transitive deps)

## Quick start

```bash
cd gl-iam-cookbook/traditional-iam/sso-glchat-production

# For an interactive browser demo (recommended for the first run):
make interactive          # setup + up + bootstrap + run-all, skips the automated demo

# For the scripted end-to-end smoke test:
make quickstart           # same as interactive + runs scripts/demo_e2e.py
```

After `make interactive`, open <http://localhost:3001>, log in as `alice@trusted-partner.example.com` / `alice-pass`, and click **Open GLChat** to see the widget auto-authenticate inside the iframe.

> `make quickstart` exercises the rate limiter (20 requests in a burst) and rotates a throwaway partner's secret. After it finishes, the in-memory rate limiter is saturated for ~60 s — if you then click "Open GLChat" and get 429, either wait a minute or run `make stop && make run-all` to reset the limiter.

Individual steps:

```bash
./setup.sh                # creates .env, generates Fernet key, runs uv sync
make up                   # start Postgres (:55432) + Redis (:56379)
make bootstrap            # create platform admin + register partner (writes keys to .env)
make run-all              # start GLChat BE, Partner BE, and static FE server
make demo                 # scripted end-to-end test (exits non-zero on any failed assertion)
make stop && make down    # tear everything down
```

> Postgres and Redis are published on non-default host ports (55432 / 56379) so this cookbook doesn't collide with other local containers that commonly bind the defaults. If either host port is already taken, edit `docker-compose.yml` + `.env`.

Browser flow after `make run-all`:

1. <http://localhost:3001> — Partner site. Log in as `alice@trusted-partner.example.com` / `alice-pass`, click **Open GLChat**.
2. Widget loads in iframe; parent posts the one-time token via `postMessage`; widget exchanges for a JWT and renders a welcome.
3. <http://localhost:3002> — GLChat admin. Log in as `admin@glchat.example.com` / `AdminPass123!`. Register new partners, rotate secrets, view the audit log.

## What is GL-IAM SDK vs application code

| Concern | Provided by GL-IAM | Provided by this cookbook |
|---|---|---|
| HMAC-SHA256 signature validation | ✅ `validate_partner_signature()` | — |
| IP allowlist (CIDR) enforcement | ✅ SDK enforces when `source_ip` passed | pass `source_ip` from middleware |
| Email-domain allowlist enforcement | ✅ SDK enforces when `email` passed | — |
| Timestamp tolerance | ✅ `tolerance_seconds` param | set to 60 s |
| Encrypted secret storage (AES-256-GCM) | ✅ automatic | — |
| Consumer-secret rotation + grace period | ✅ `rotate_consumer_secret()` | admin UI + API surface |
| JWT session issuance | ✅ `create_session()` | — |
| JIT user provisioning | ✅ `create_user` + `link_external_identity` | — |
| Audit event persistence | ✅ `DatabaseAuditHandler` | emit app-level SSO events |
| One-time token store (replay-proof) | — | `services/token_store.py` (Redis) |
| Nonce replay store | — | `services/nonce_store.py` (Redis) |
| Rate limiting per `consumer_key` | — | `middleware/rate_limit.py` (SlowAPI) |
| Dynamic CSP `frame-ancestors` | — | `middleware/csp.py` |
| `max_users` / `allowed_roles` enforcement | stored; not enforced | `services/sso_service.py` |
| `postMessage` handshake | — | `frontends/*.html` |

## Security reminders still OUT of scope

These matter in production but are explicitly out of this cookbook's scope — either because they require infra this cookbook doesn't set up, or because they are orthogonal concerns:

- **TLS termination** — every transport here is plain HTTP. Use a reverse proxy (nginx, Envoy, AWS ALB) with real certs. Then enable `Secure` on cookies and bind cookies to `SameSite=None`.
- **Secret manager** for `GLCHAT_ENCRYPTION_KEY` and `GLCHAT_SECRET_KEY`. See [`gliam` CLI `--database-url-secret`](https://github.com/GDP-ADMIN/gl-sdk/blob/main/libs/gl-iam/gl_iam/cli/main.py) for an AWS Secrets Manager pattern.
- **WAF / DDoS** — rate limiting here is per-`consumer_key` in-process; add a CDN/WAF layer in front.
- **Clock sync** — both sides must run NTP; the 60 s window assumes so.
- **Log sinks / SIEM** — this example uses `ConsoleAuditHandler` + `DatabaseAuditHandler`. Production should also add [OpenTelemetry](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/guides/audit-trail/opentelemetry) + a forwarder.
- **Platform admin auth method** — admin logs in via password for demo simplicity. Real GLChat admin should use MFA or an existing SSO provider.

## References

- [GL-IAM SDK (main branch)](https://github.com/GDP-ADMIN/gl-sdk)
- [IdP-Initiated vs SP-Initiated SSO — architecture doc](https://github.com/GDP-ADMIN/gl-sdk/blob/main/libs/gl-iam/docs/architecture/IDP_VS_SP_INITIATED_SSO_COMPARISON.md)
- [IdP-Initiated SSO planning doc](https://github.com/GDP-ADMIN/gl-sdk/blob/main/libs/gl-iam/docs/planning/20-idp-initiated-sso.md)
- [GL-IAM Cookbook root](https://github.com/gdplabs/gl-iam-cookbook)
- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam)
- Sibling examples: [`sso-token-exchange`](https://github.com/gdplabs/gl-iam-cookbook/tree/main/traditional-iam/sso-token-exchange) · [`sso-jwt-bridge`](https://github.com/gdplabs/gl-iam-cookbook/tree/main/traditional-iam/sso-jwt-bridge) · [`audit-trail-fastapi`](https://github.com/gdplabs/gl-iam-cookbook/tree/main/traditional-iam/audit-trail-fastapi)
