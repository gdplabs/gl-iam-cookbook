# Keycloak DPoP + mTLS Lab (uv)

This folder contains a small Python lab to learn DPoP and mTLS concepts, check
StackAuth compatibility options, and issue sender-constrained tokens with
Keycloak. The code is intentionally minimal and focuses on generating DPoP
proofs and making mTLS requests with httpx.

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

You can use mTLS client authentication together with DPoP token binding for
defense-in-depth. Do not assume that enabling both token-binding modes produces
both confirmation members; verify the issued `cnf` claim for your AS version.

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
├── realm/
│   └── realm-export.json       # Keycloak realm with pre-configured clients
├── certs/                      # Generated certificates (gitignored)
├── docs/                       # Additional documentation
├── tests/                      # Unit tests for DPoP
├── docker-compose.yml          # Keycloak with HTTPS/mTLS setup
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

# Start Keycloak
docker compose up -d

# Wait for the realm import, then verify HTTPS using the generated CA
curl --cacert ./certs/ca.crt \
  https://localhost:8443/realms/dpop-lab/.well-known/openid-configuration
```

### Run Tests

```bash
uv run pytest -v

## With the Docker stack running, verify token claims and rejection cases
uv run python scripts/verify-bindings.py
```

## 5) Hands-on Flows

### Basic Token Request (No DPoP/mTLS)

```bash
uv run keycloak-lab token \
  --token-url https://localhost:8443/realms/dpop-lab/protocol/openid-connect/token \
  --client-id lab-client \
  --client-secret lab-secret \
  --ca ./certs/ca.crt
```

### DPoP-only Flow

```bash
# 1. Generate DPoP key pair
uv run keycloak-lab gen-key --private-key dpop_private.pem --public-jwk dpop_public.jwk

# 2. Request token with DPoP proof
uv run keycloak-lab token \
  --token-url https://localhost:8443/realms/dpop-lab/protocol/openid-connect/token \
  --client-id dpop-client \
  --client-secret dpop-secret \
  --scope "openid profile" \
  --ca ./certs/ca.crt \
  --dpop-private-key dpop_private.pem

# 3. Call Keycloak UserInfo as a DPoP-protected resource
uv run keycloak-lab call \
  --url https://localhost:8443/realms/dpop-lab/protocol/openid-connect/userinfo \
  --access-token ACCESS_TOKEN \
  --dpop-private-key dpop_private.pem \
  --ca ./certs/ca.crt
```

### mTLS-only Flow

Keycloak terminates TLS directly so it can validate the certificate and place
its SHA-256 thumbprint in the token:

```bash
uv run keycloak-lab token \
  --token-url https://localhost:8443/realms/dpop-lab/protocol/openid-connect/token \
  --client-id mtls-client \
  --client-secret mtls-secret \
  --scope "openid profile" \
  --cert ./certs/client.crt \
  --key ./certs/client.key \
  --ca ./certs/ca.crt
```

Use the same certificate when presenting the token to UserInfo:

```bash
curl --cacert ./certs/ca.crt \
  --cert ./certs/client.crt \
  --key ./certs/client.key \
  --header "Authorization: Bearer ACCESS_TOKEN" \
  https://localhost:8443/realms/dpop-lab/protocol/openid-connect/userinfo
```

### mTLS Client Authentication + DPoP Token Binding

This client uses the certificate instead of a client secret for OAuth client
authentication. The access token is sender-constrained to the DPoP key through
`cnf.jkt`; the certificate authenticates the client at the token endpoint.

```bash
uv run keycloak-lab token \
  --token-url https://localhost:8443/realms/dpop-lab/protocol/openid-connect/token \
  --client-id combined-client \
  --scope "openid profile" \
  --cert ./certs/client.crt \
  --key ./certs/client.key \
  --ca ./certs/ca.crt \
  --dpop-private-key dpop_private.pem
```

Expected results:

| Client            | Token type | Expected `cnf`              |
| ----------------- | ---------- | --------------------------- |
| `lab-client`      | Bearer     | absent                      |
| `dpop-client`     | DPoP       | `jkt`                       |
| `mtls-client`     | Bearer     | `x5t#S256`                  |
| `combined-client` | DPoP       | `jkt` (mTLS authenticates)  |

Keycloak rejects `dpop-client` without a DPoP proof, `mtls-client` without a
certificate, and `combined-client` unless both its certificate and DPoP proof
are present. The Keycloak UserInfo endpoint is the included protected-resource
target; the `call` command can also be used with another DPoP-aware API.

## 6) Keycloak Admin

Open the admin console at `http://localhost:8080/admin`:

- Username: `admin`
- Password: `admin`

The realm `dpop-lab` is imported automatically with four clients:

- Baseline: `lab-client` / Secret: `lab-secret`
- DPoP-bound: `dpop-client` / Secret: `dpop-secret`
- Certificate-bound: `mtls-client` / Secret: `mtls-secret`
- mTLS-authenticated DPoP: `combined-client` / no client secret
- User: `lab-user` / Password: `lab-pass`

### Endpoints

| Endpoint       | URL                                              |
| -------------- | ------------------------------------------------ |
| Keycloak HTTP  | `http://localhost:8080`                          |
| Keycloak HTTPS | `https://localhost:8443`                         |
| Token Endpoint | `/realms/dpop-lab/protocol/openid-connect/token` |

## 7) Cleanup

```bash
# Stop containers
docker compose down

# Remove generated files (optional)
rm -rf certs/ dpop_private.pem dpop_public.jwk
```

## 8) Notes

- `start-dev` is for this local lab only. Keycloak terminates HTTPS directly and
  requests client certificates so certificate-bound tokens can be issued.
- The pinned Keycloak 26.4 release has supported DPoP enabled. The realm makes
  DPoP mandatory only for clients that are intended to receive DPoP tokens.
- `combined-client` deliberately uses mTLS for client authentication and DPoP
  for token binding. It does not claim simultaneous `jkt` and `x5t#S256`
  binding.
- The scripts use the standard OAuth token endpoint shape used by Keycloak.
- If you need a token exchange flow or a brokered setup for StackAuth,
  keep the DPoP binding at the token-issuing AS and verify `cnf.jkt` at the RS.

## References

- [RFC 9449 - OAuth 2.0 DPoP](https://datatracker.ietf.org/doc/html/rfc9449)
- [RFC 8705 - OAuth 2.0 Mutual-TLS](https://datatracker.ietf.org/doc/html/rfc8705)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
