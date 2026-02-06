#!/usr/bin/env bash
# ==============================================================================
# PKI Certificate Generation Script for DPoP + mTLS Lab
# ==============================================================================
#
# This script generates a complete PKI (Public Key Infrastructure) for testing
# mTLS (Mutual TLS) authentication as specified in RFC 8705.
#
# Generated Certificates:
# 1. CA (Certificate Authority):
#    - Root of trust for the PKI
#    - Signs both server and client certificates
#    - Used by clients to verify server, and by server to verify clients
#
# 2. Server Certificate:
#    - Presented by Nginx during TLS handshake
#    - Allows clients to verify they're connecting to the right server
#    - Includes SAN (Subject Alternative Name) for localhost
#
# 3. Client Certificate:
#    - Presented by the client during mutual TLS handshake
#    - Proves the client's identity to the server
#    - Has Extended Key Usage: clientAuth
#
# PKI Trust Flow:
#   CA (lab-ca)
#   ├── signs → Server Cert (localhost) 
#   │           └── Server presents this to clients
#   └── signs → Client Cert (lab-client)
#               └── Client presents this to server for mTLS
#
# RFC 8705 Section 2 Requirements:
# - The TLS connection MUST use mutual TLS X.509 certificate authentication
# - The client Certificate and CertificateVerify messages are sent during handshake
# - The authorization server validates the certificate against expected credentials
#
# ==============================================================================

set -euo pipefail

# Get the project root directory (parent of scripts/)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/certs"

# Create output directory
mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

# ==============================================================================
# 1. Certificate Authority (CA)
# ==============================================================================
# Generate a self-signed CA certificate with:
# - RSA 4096-bit key (strong security)
# - Valid for 10 years (3650 days)
# - No password protection (-nodes) for lab convenience
echo "Generating CA certificate..."
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout ca.key -out ca.crt -subj "/CN=lab-ca"

# ==============================================================================
# 2. Server Certificate (for Nginx)
# ==============================================================================
# Generate a CSR (Certificate Signing Request) for the server
echo "Generating server certificate..."
openssl req -newkey rsa:2048 -nodes \
  -keyout server.key -out server.csr -subj "/CN=localhost"

# Create extensions file for the server certificate
# - SAN: Required for modern TLS (CN alone is deprecated)
# - serverAuth: Extended Key Usage for TLS servers
cat > server.ext <<EOF
subjectAltName=DNS:localhost,IP:127.0.0.1
extendedKeyUsage=serverAuth
EOF

# Sign the server certificate with the CA
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 365 -sha256 -extfile server.ext

# ==============================================================================
# 3. Client Certificate (for mTLS authentication)
# ==============================================================================
# Generate a CSR for the client
echo "Generating client certificate..."
openssl req -newkey rsa:2048 -nodes \
  -keyout client.key -out client.csr -subj "/CN=lab-client"

# Create extensions file for the client certificate
# - clientAuth: Extended Key Usage for TLS clients (RFC 8705)
# This EKU is important - it tells the server this cert is for client auth
cat > client.ext <<EOF
extendedKeyUsage=clientAuth
EOF

# Sign the client certificate with the CA
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out client.crt -days 365 -sha256 -extfile client.ext

# ==============================================================================
# Cleanup temporary files
# ==============================================================================
rm -f *.csr *.ext ca.srl

echo "Wrote CA, server, and client certs to $OUT_DIR"
echo ""
echo "Files created:"
echo "  - ca.crt, ca.key        : Certificate Authority"
echo "  - server.crt, server.key: Server certificate for Nginx"
echo "  - client.crt, client.key: Client certificate for mTLS"
