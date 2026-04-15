"""Console pretty-printer for demo clarity.

Prints visually banded, colored blocks for each SSO step so the terminal
tail-f tells the same story the browser trace panel tells.
"""

from __future__ import annotations

import os
import sys
from typing import Any

_ENABLED = sys.stdout.isatty() or os.environ.get("FORCE_COLOR") == "1"

# ANSI color codes (no color if not a TTY and FORCE_COLOR unset).
class C:
    RESET = "\033[0m" if _ENABLED else ""
    DIM = "\033[2m" if _ENABLED else ""
    BOLD = "\033[1m" if _ENABLED else ""
    CYAN = "\033[96m" if _ENABLED else ""
    BLUE = "\033[94m" if _ENABLED else ""
    GREEN = "\033[92m" if _ENABLED else ""
    YELLOW = "\033[93m" if _ENABLED else ""
    RED = "\033[91m" if _ENABLED else ""
    MAGENTA = "\033[95m" if _ENABLED else ""


_WIDTH = 90


def banner(title: str, color: str = C.CYAN, subtitle: str | None = None) -> None:
    """Print a boxed step banner."""
    bar = "─" * (_WIDTH - 2)
    print(f"\n{color}┌{bar}┐{C.RESET}")
    print(f"{color}│{C.RESET} {C.BOLD}{title}{C.RESET}".ljust(_WIDTH + len(C.BOLD) + len(C.RESET) + len(color) + len(C.RESET) - 1) + f"{color}│{C.RESET}")
    if subtitle:
        print(f"{color}│{C.RESET} {C.DIM}{subtitle}{C.RESET}".ljust(_WIDTH + len(C.DIM) + len(C.RESET) + len(color) + len(C.RESET) - 1) + f"{color}│{C.RESET}")
    print(f"{color}└{bar}┘{C.RESET}")


def kv(label: str, value: Any, color: str = C.BLUE) -> None:
    v = value if isinstance(value, str) else repr(value)
    print(f"  {color}{label:<22}{C.RESET} {v}")


def sdk(action: str, detail: str = "", ok: bool = True) -> None:
    tag = f"{C.MAGENTA}[SDK]{C.RESET}"
    status = f"{C.GREEN}✓{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
    msg = f"  {tag} {status} {C.BOLD}{action}{C.RESET}"
    if detail:
        msg += f"  {C.DIM}→ {detail}{C.RESET}"
    print(msg)


def app(action: str, detail: str = "", ok: bool = True) -> None:
    tag = f"{C.YELLOW}[APP]{C.RESET}"
    status = f"{C.GREEN}✓{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
    msg = f"  {tag} {status} {C.BOLD}{action}{C.RESET}"
    if detail:
        msg += f"  {C.DIM}→ {detail}{C.RESET}"
    print(msg)


def warn(msg: str) -> None:
    print(f"  {C.YELLOW}⚠  {msg}{C.RESET}")


def err(msg: str) -> None:
    print(f"  {C.RED}✗  {msg}{C.RESET}")


def done(msg: str) -> None:
    print(f"  {C.GREEN}✓  {msg}{C.RESET}")


def divider() -> None:
    print(f"{C.DIM}{'·' * _WIDTH}{C.RESET}")
