from __future__ import annotations

import argparse
import json
import sys

from .dpop import load_private_pem
from .keygen import generate_and_save
from .mtls_client import call_resource, request_token_mtls


def _add_common_cert_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cert", help="Client certificate PEM path")
    parser.add_argument("--key", help="Client private key PEM path")
    parser.add_argument("--ca", help="CA bundle/CA cert PEM path for TLS verify")


def cmd_gen_key(args: argparse.Namespace) -> int:
    generate_and_save(args.private_key, args.public_jwk)
    print(f"Wrote {args.private_key} and {args.public_jwk}")
    return 0


def cmd_token(args: argparse.Namespace) -> int:
    dpop_key = load_private_pem(args.dpop_private_key) if args.dpop_private_key else None
    payload = request_token_mtls(
        args.token_url,
        args.client_id,
        client_secret=args.client_secret,
        scope=args.scope,
        cert=args.cert,
        key=args.key,
        ca=args.ca,
        dpop_private_key=dpop_key,
        dpop_nonce=args.dpop_nonce,
    )
    print(json.dumps(payload, indent=2))
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    dpop_key = load_private_pem(args.dpop_private_key)
    response = call_resource(
        args.url,
        args.access_token,
        dpop_key,
        method=args.method,
        cert=args.cert,
        key=args.key,
        ca=args.ca,
    )
    print(f"Status: {response.status_code}")
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        print(json.dumps(response.json(), indent=2))
    else:
        print(response.text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keycloak-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen_key = subparsers.add_parser("gen-key", help="Generate DPoP EC key pair")
    gen_key.add_argument("--private-key", required=True, help="Output PEM path")
    gen_key.add_argument("--public-jwk", required=True, help="Output JWK path")
    gen_key.set_defaults(func=cmd_gen_key)

    token = subparsers.add_parser("token", help="Request access token with mTLS")
    token.add_argument("--token-url", required=True)
    token.add_argument("--client-id", required=True)
    token.add_argument("--client-secret")
    token.add_argument("--scope")
    token.add_argument("--dpop-private-key", help="PEM path for DPoP key")
    token.add_argument("--dpop-nonce", help="Nonce from DPoP-Nonce header if required")
    _add_common_cert_args(token)
    token.set_defaults(func=cmd_token)

    call = subparsers.add_parser("call", help="Call resource with DPoP + optional mTLS")
    call.add_argument("--url", required=True)
    call.add_argument("--access-token", required=True)
    call.add_argument("--dpop-private-key", required=True, help="PEM path for DPoP key")
    call.add_argument("--method", default="GET")
    _add_common_cert_args(call)
    call.set_defaults(func=cmd_call)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
