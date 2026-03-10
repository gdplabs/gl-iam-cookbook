"""
DelegationToken Inspector — Decode and pretty-print JWT claims.

Usage:
    uv run python decode_token.py <jwt-string>
    make decode TOKEN=<jwt-string>
"""

import base64
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

# Colors
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def decode_jwt_unverified(token: str) -> dict | None:
    """Decode JWT payload without verification (for display even if expired)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Decode payload (part 2), add padding
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return None


def decode_jwt_header(token: str) -> dict | None:
    """Decode JWT header."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64 = parts[0]
        header_b64 += "=" * (4 - len(header_b64) % 4)
        header_bytes = base64.urlsafe_b64decode(header_b64)
        return json.loads(header_bytes)
    except Exception:
        return None


def format_time(ts: int | float | None) -> str:
    if ts is None:
        return "(not set)"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_remaining(exp: int | float | None) -> str:
    if exp is None:
        return "(no expiry)"
    now = datetime.now(timezone.utc).timestamp()
    diff = exp - now
    if diff <= 0:
        return f"{RED}EXPIRED{NC}"
    minutes = int(diff // 60)
    seconds = int(diff % 60)
    return f"{minutes}m {seconds}s"


def main():
    if len(sys.argv) < 2:
        print(f"Usage: uv run python {sys.argv[0]} <jwt-token>")
        sys.exit(1)

    token = sys.argv[1].strip()
    secret_key = os.getenv("SECRET_KEY", "")

    # Try verified decode first
    verified = False
    payload = None

    if secret_key:
        try:
            from gl_iam.core.delegation_utils import decode_delegation_jwt

            result = decode_delegation_jwt(token, secret_key)
            if result.is_ok:
                payload = result.value
                verified = True
        except ImportError:
            pass
        except Exception:
            pass

    # Fall back to unverified decode
    if payload is None:
        payload = decode_jwt_unverified(token)

    if payload is None:
        print(f"\n  {RED}Error:{NC} Could not decode token. Is it a valid JWT?")
        sys.exit(1)

    header = decode_jwt_header(token)

    # Display
    print()
    print(f"{BOLD}{CYAN}{'=' * 66}{NC}")
    print(f"{BOLD}{CYAN}               DelegationToken Inspection{NC}")
    print(f"{BOLD}{CYAN}{'=' * 66}{NC}")

    # Verification status
    if verified:
        print(f"\n  {GREEN}Signature verified{NC} with SECRET_KEY from .env")
    else:
        if secret_key:
            print(f"\n  {YELLOW}WARNING: Signature verification failed{NC}")
            print(f"  {DIM}Showing decoded payload (unverified){NC}")
        else:
            print(f"\n  {YELLOW}No SECRET_KEY in .env — showing unverified payload{NC}")

    # Token info
    print(f"\n  Token: {DIM}{token}{NC} ({len(token)} chars)")
    if header:
        print(f"  Algorithm: {header.get('alg', 'unknown')}")
    print(f"  Issuer: {payload.get('iss', '(not set)')}")

    # Subject & Task
    print(f"\n{BOLD}── Subject & Task {'─' * 48}{NC}")
    print(f"  Agent ID:          {payload.get('sub', '(not set)')}")
    task = payload.get("task", {})
    if isinstance(task, dict):
        print(f"  Task ID:           {task.get('id', '(not set)')}")
        print(f"  Task Purpose:      {task.get('purpose', '(not set)')}")
        print(f"  Data Sensitivity:  {task.get('data_sensitivity', '(not set)')}")
    elif payload.get("task_id"):
        print(f"  Task ID:           {payload.get('task_id')}")

    # Scopes
    scopes = payload.get("scopes", payload.get("scope", []))
    if isinstance(scopes, str):
        scopes = scopes.split()
    print(f"\n{BOLD}── Scopes {'─' * 57}{NC}")
    if scopes:
        for s in scopes:
            print(f"  {GREEN}\u2713{NC} {s}")
    else:
        print(f"  {DIM}(none){NC}")

    # Delegation Chain
    chain = payload.get("delegation_chain", [])
    if chain:
        print(f"\n{BOLD}── Delegation Chain {'─' * 47}{NC}")
        for i, link in enumerate(chain, 1):
            link_type = link.get("type", "unknown")
            link_sub = link.get("sub", "unknown")
            link_scopes = link.get("scopes", [])
            if isinstance(link_scopes, list) and len(link_scopes) > 3:
                scope_str = ", ".join(link_scopes[:3]) + ", ..."
            elif isinstance(link_scopes, list):
                scope_str = ", ".join(link_scopes)
            else:
                scope_str = str(link_scopes)
            print(f"  Link {i}: {link_type:8s} -> {link_sub}  scopes: [{scope_str}]")

    # Act claim (RFC 8693)
    act = payload.get("act")
    if act:
        print(f"\n{BOLD}── IETF 'act' Claim (RFC 8693) {'─' * 36}{NC}")
        print(f"  {json.dumps(act)}")

    # Timing
    print(f"\n{BOLD}── Timing {'─' * 57}{NC}")
    print(f"  Issued At:   {format_time(payload.get('iat'))}")
    print(f"  Expires At:  {format_time(payload.get('exp'))}")
    print(f"  Remaining:   {format_remaining(payload.get('exp'))}")

    # Resource Constraints
    constraints = payload.get("resource_constraints")
    print(f"\n{BOLD}── Resource Constraints {'─' * 44}{NC}")
    if constraints:
        print(f"  {json.dumps(constraints, indent=2)}")
    else:
        print(f"  {DIM}(none){NC}")

    # Task Metadata
    metadata = {}
    if isinstance(task, dict):
        metadata = task.get("metadata", {})
    if not metadata:
        metadata = payload.get("metadata", {})
    print(f"\n{BOLD}── Task Metadata {'─' * 50}{NC}")
    if metadata:
        for k, v in metadata.items():
            print(f"  {k}: {v}")
    else:
        print(f"  {DIM}(none){NC}")

    # Raw claims
    print(f"\n{BOLD}── Raw Claims (JSON) {'─' * 46}{NC}")
    print(f"  {json.dumps(payload, indent=2, default=str)}")

    print()


if __name__ == "__main__":
    main()
