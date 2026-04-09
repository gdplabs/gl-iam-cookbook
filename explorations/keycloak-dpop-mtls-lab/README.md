# Keycloak DPoP + mTLS Lab (uv)

This folder contains a small Python lab to help you learn DPoP and mTLS concepts,
check StackAuth compatibility options, and try a hands-on flow with Keycloak.
The code is intentionally minimal and focuses on generating DPoP proofs and
making mTLS requests with httpx.

## 1) Concepts: DPoP vs mTLS

**DPoP (Demonstration of Proof-of-Possession) - [RFC 9449](https://datatracker.ietf.org/doc/html/rfc9449):**

- Per-request proof (a signed JWT) that binds an HTTP request to a key pair.
- The client signs a DPoP proof with its private key and sends it in a `DPoP` header.
- A DPoP-capable Authorization Server (AS) can bind the access token to the key
  by including a confirmation claim (`cnf.jkt`). The Resource Server (RS) then
  checks that each request also proves possession of the same key.

**mTLS (Mutual TLS) - [RFC 8705](https://datatracker.ietf.org/doc/html/rfc8705):**

- Transport-level authentication using client certificates.
- The client proves possession of a private key during the TLS handshake.
- The AS and/or RS can authenticate the client based on the presented certificate.

**When to use which:**

| Feature           | DPoP                         | mTLS                             |
| ----------------- | ---------------------------- | -------------------------------- |
| Best for          | Public clients (mobile, SPA) | Backend services, M2M            |
| Per-request proof | ✅ Yes                       | ❌ No                            |
| Requires PKI      | ❌ No                        | ✅ Yes                           |
| Token binding     | `cnf.jkt` (key thumbprint)   | `cnf.x5t#S256` (cert thumbprint) |

You can combine both for defense-in-depth, but you must verify that your AS and
RS support the necessary token binding behaviors.

> 📊 **See also:** [docs/dpop_mtls_diagrams.md](docs/dpop_mtls_diagrams.md) for visual flow diagrams.

## 2) StackAuth Compatibility

If a consumer already uses StackAuth as the Authorization Server:

> ⚠️ **StackAuth does NOT natively support DPoP or mTLS token binding.**

**Practical options:**

1. If StackAuth supports DPoP/mTLS token binding, use it directly.
2. If not, place a broker (e.g., Keycloak) in front to exchange StackAuth tokens
   for DPoP/mTLS-bound tokens that your RS accepts.
3. If token binding is not possible, enforce mTLS at the gateway for
   client-to-gateway traffic and use normal Bearer tokens downstream.

> 📖 **See also:** [docs/stackauth_compatibility.md](docs/stackauth_compatibility.md) for detailed analysis.

## 3) Project Layout

```
keycloak/
├── src/keycloak_dpop_mtls/     # DPoP + mTLS helper code
│   ├── dpop.py                 # DPoP proof generation (RFC 9449)
│   ├── mtls_client.py          # mTLS HTTP client (RFC 8705)
│   ├── keygen.py               # Key pair generation
│   └── cli.py                  # Command-line interface
├── scripts/
│   └── gen-certs.sh            # PKI certificate generation
├── nginx/
│   └── nginx.conf              # mTLS reverse proxy config
├── realm/
│   └── realm-export.json       # Keycloak realm with pre-configured client
├── certs/                      # Generated certificates (gitignored)
├── docs/                       # Additional documentation
├── tests/                      # Unit tests for DPoP
├── docker-compose.yml          # Keycloak + Nginx setup
└── pyproject.toml              # Python dependencies (uv)
```

## 4) Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose

### Setup

```bash
# Install dependencies
uv sync --dev

# Generate certificates for mTLS
./scripts/gen-certs.sh

# Start Keycloak + Nginx
docker compose up -d

# Wait ~15 seconds for Keycloak to start, then verify
curl http://localhost:8080/health/ready
```

### Run Tests

```bash
uv run pytest -v
```

## 5) Hands-on Flows

### Basic Token Request (No DPoP/mTLS)

```bash
uv run keycloak-lab token \
  --token-url http://localhost:8080/realms/dpop-lab/protocol/openid-connect/token \
  --client-id lab-client \
  --client-secret lab-secret
```

### DPoP-only Flow

```bash
# 1. Generate DPoP key pair
uv run keycloak-lab gen-key --private-key dpop_private.pem --public-jwk dpop_public.jwk

# 2. Request token with DPoP proof
uv run keycloak-lab token \
  --token-url http://localhost:8080/realms/dpop-lab/protocol/openid-connect/token \
  --client-id lab-client \
  --client-secret lab-secret \
  --dpop-private-key dpop_private.pem

# 3. Call a resource with DPoP (replace with your API)
uv run keycloak-lab call \
  --url https://API_HOST/protected \
  --access-token ACCESS_TOKEN \
  --dpop-private-key dpop_private.pem
```

### mTLS-only Flow

Uses the Nginx proxy on `https://localhost:8443` (requires cert generation first):

```bash
uv run keycloak-lab token \
  --token-url https://localhost:8443/realms/dpop-lab/protocol/openid-connect/token \
  --client-id lab-client \
  --client-secret lab-secret \
  --cert ./certs/client.crt \
  --key ./certs/client.key \
  --ca ./certs/ca.crt
```

### Combined DPoP + mTLS

```bash
uv run keycloak-lab token \
  --token-url https://localhost:8443/realms/dpop-lab/protocol/openid-connect/token \
  --client-id lab-client \
  --client-secret lab-secret \
  --cert ./certs/client.crt \
  --key ./certs/client.key \
  --ca ./certs/ca.crt \
  --dpop-private-key dpop_private.pem
```

## 6) Keycloak Admin

Open the admin console at `http://localhost:8080/admin`:

- Username: `admin`
- Password: `admin`

The realm `dpop-lab` is imported automatically with:

- Client: `lab-client` / Secret: `lab-secret`
- User: `lab-user` / Password: `lab-pass`

### Endpoints

| Endpoint       | URL                                              |
| -------------- | ------------------------------------------------ |
| Keycloak HTTP  | `http://localhost:8080`                          |
| Nginx mTLS     | `https://localhost:8443`                         |
| Token Endpoint | `/realms/dpop-lab/protocol/openid-connect/token` |

## 7) Cleanup

```bash
# Stop containers
docker compose down

# Remove generated files (optional)
rm -rf certs/ dpop_private.pem dpop_public.jwk
```

## 8) Notes

- `start-dev` runs Keycloak on HTTP. The included Nginx proxy terminates TLS and
  requires a client certificate on the token endpoint only.
- If your Keycloak version supports DPoP (v21+), enable the feature and ensure
  the AS issues DPoP-bound tokens (`cnf.jkt`).
- The scripts use the standard OAuth token endpoint shape used by Keycloak.
- If you need a token exchange flow or a brokered setup for StackAuth,
  keep the DPoP binding at the token-issuing AS and verify `cnf.jkt` at the RS.

## References

- [RFC 9449 - OAuth 2.0 DPoP](https://datatracker.ietf.org/doc/html/rfc9449)
- [RFC 8705 - OAuth 2.0 Mutual-TLS](https://datatracker.ietf.org/doc/html/rfc8705)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
