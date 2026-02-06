# DPoP & mTLS Flow Diagrams

This document provides visual diagrams explaining how DPoP and mTLS work.

---

## DPoP Token Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant AS as Authorization Server
    participant RS as Resource Server

    Note over Client: 1. Generate EC key pair
    Client->>Client: generate_ec_key()

    Note over Client: 2. Create DPoP proof for token request
    Client->>Client: build_dpop_proof(htu=token_url, htm="POST")

    Client->>AS: POST /token<br/>DPoP: [signed JWT]<br/>client_id, client_secret

    Note over AS: 3. Validate DPoP proof
    AS->>AS: Verify JWT signature with jwk from header
    AS->>AS: Check jti is unique (replay protection)
    AS->>AS: Verify htu matches request URL
    AS->>AS: Verify htm matches "POST"
    AS->>AS: Check iat is recent

    Note over AS: 4. Issue DPoP-bound token
    AS->>AS: Compute jkt = SHA256(jwk)
    AS-->>Client: access_token with cnf.jkt claim

    Note over Client: 5. Create DPoP proof for resource request
    Client->>Client: build_dpop_proof(htu=resource_url, htm="GET", ath=hash(token))

    Client->>RS: GET /protected<br/>Authorization: DPoP [token]<br/>DPoP: [signed JWT with ath]

    Note over RS: 6. Validate token binding
    RS->>RS: Verify JWT signature with jwk
    RS->>RS: Check cnf.jkt matches jwk thumbprint
    RS->>RS: Verify ath matches hash of token
    RS-->>Client: 200 OK + Protected Resource
```

---

## DPoP Proof JWT Structure

```mermaid
graph TD
    subgraph "DPoP Proof JWT"
        subgraph "Header"
            H1["typ: dpop+jwt"]
            H2["alg: ES256"]
            H3["jwk: {kty, crv, x, y}"]
        end
        subgraph "Payload"
            P1["jti: unique-id"]
            P2["htm: POST|GET"]
            P3["htu: https://..."]
            P4["iat: timestamp"]
            P5["ath: token-hash<br/>(resource calls only)"]
            P6["nonce: server-nonce<br/>(if required)"]
        end
        subgraph "Signature"
            S1["ECDSA with private key"]
        end
    end
```

---

## mTLS Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant Nginx as Nginx (mTLS Proxy)
    participant KC as Keycloak

    Note over Client,Nginx: TLS Handshake with mutual authentication

    Client->>Nginx: ClientHello
    Nginx-->>Client: ServerHello + Server Certificate
    Nginx-->>Client: CertificateRequest
    Client->>Nginx: Client Certificate + CertificateVerify

    Note over Nginx: Verify client cert against CA
    Nginx->>Nginx: Validate cert chain
    Nginx->>Nginx: Check ssl_client_verify = SUCCESS

    alt Certificate Valid
        Nginx-->>Client: Finished (TLS established)
        Client->>Nginx: POST /token (encrypted)
        Nginx->>KC: Forward to Keycloak
        KC-->>Nginx: Token Response
        Nginx-->>Client: Token Response (encrypted)
    else Certificate Invalid/Missing
        Nginx-->>Client: 403 Forbidden
    end
```

---

## PKI Certificate Trust Chain

```mermaid
graph TB
    subgraph "Certificate Authority"
        CA["lab-ca (CA)<br/>Self-signed root"]
    end

    subgraph "Server PKI"
        SC["server.crt<br/>CN=localhost<br/>EKU: serverAuth"]
    end

    subgraph "Client PKI"
        CC["client.crt<br/>CN=lab-client<br/>EKU: clientAuth"]
    end

    CA -->|signs| SC
    CA -->|signs| CC

    SC -.->|"presented to"| Client2["Client"]
    CC -.->|"presented to"| Server["Server (Nginx)"]
```

---

## Combined DPoP + mTLS Flow

```mermaid
sequenceDiagram
    participant Client
    participant Nginx as Nginx (mTLS)
    participant KC as Keycloak

    Note over Client,Nginx: 1. mTLS Handshake
    Client->>Nginx: TLS + Client Cert
    Nginx->>Nginx: Verify cert against CA

    Note over Client: 2. DPoP proof generation
    Client->>Client: build_dpop_proof()

    Client->>Nginx: POST /token<br/>DPoP: [proof JWT]<br/>+ mTLS cert
    Nginx->>KC: Forward (with X-Client-Cert header)

    Note over KC: 3. Dual validation
    KC->>KC: Validate DPoP proof
    KC->>KC: Optionally bind to cert

    KC-->>Nginx: Token (cnf.jkt + optional cnf.x5t#S256)
    Nginx-->>Client: Token Response
```

---

## Security Comparison

| Feature                | Bearer Token | DPoP | mTLS | DPoP + mTLS |
| ---------------------- | ------------ | ---- | ---- | ----------- |
| Token theft protection | ❌           | ✅   | ✅   | ✅✅        |
| Per-request proof      | ❌           | ✅   | ❌   | ✅          |
| Channel binding        | ❌           | ❌   | ✅   | ✅          |
| Public client support  | ✅           | ✅   | ⚠️   | ⚠️          |
| No cert infrastructure | ✅           | ✅   | ❌   | ❌          |
| Replay protection      | ❌           | ✅   | ✅   | ✅✅        |
