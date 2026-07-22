"""Reusable scope gate for Digital Employee tools.

This is the drop-in piece. A DE vertical adds one decorator to an existing
LangChain tool class and that tool can no longer run outside the scopes the
human actually delegated:

    @requires_scope("google_docs:write")
    class GoogleDocsCreateDocumentTool(BaseTool):
        ...unchanged...

The gate answers the question AIP cannot answer today: *"which scope does
tool X need?"*. AIP already knows which tools an agent HAS (it derives an
agent's ``allowed_scopes`` from its attached tool names), and it already
validates and propagates a delegation token. What no layer checks yet is
whether the token presented for this run actually carries the scope the tool
about to execute requires. That check is what lives here.

The delegation token is carried in a ``ContextVar`` rather than a tool
argument, because a DE vertical does not control how the agent framework
invokes its tools. The runtime sets the context once per run; every tool
called inside that run reads it. When AIP's delegation propagation is
enabled, the same context is populated from ``metadata["delegation"]``
instead of being minted locally -- the tool code does not change.
"""

from __future__ import annotations

import functools
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from gl_iam import DelegationToken, is_permitted

# Marker attribute the decorator writes onto a tool class. Deliberately not a
# pydantic field: BaseTool is a pydantic model and we do not want to change
# its schema, only tag it.
REQUIRED_SCOPE_ATTR = "__gl_iam_required_scope__"


@dataclass
class GateDecision:
    """One allow/deny decision made by the gate, for the audit timeline."""

    tool_name: str
    required_scope: str
    allowed: bool
    reason: str
    task_id: str | None = None
    root_principal: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision for the console."""
        return {
            "tool_name": self.tool_name,
            "required_scope": self.required_scope,
            "allowed": self.allowed,
            "reason": self.reason,
            "task_id": self.task_id,
            "root_principal": self.root_principal,
            "decided_at": self.decided_at.isoformat(),
        }


@dataclass
class DelegationContext:
    """The delegation token in force for the current DE run.

    Attributes:
        token: The validated delegation token. ``None`` means no delegation
            was established, which the gate treats as deny-all (fail closed).
        decisions: Every gate decision made during this run, in order.
        requested_scopes: Scopes the gate denied because they were missing.
            The console turns these into pending access requests for the user.
    """

    token: DelegationToken | None = None
    decisions: list[GateDecision] = field(default_factory=list)
    requested_scopes: set[str] = field(default_factory=set)

    @property
    def effective_scopes(self) -> list[str]:
        """Scopes the leaf agent can actually use, after chain attenuation."""
        if self.token is None:
            return []
        return sorted(self.token.chain.effective_scopes())

    def check(self, tool_name: str, required_scope: str) -> GateDecision:
        """Decide whether a tool requiring ``required_scope`` may run.

        Fails closed: no token, an expired token, or a token whose chain does
        not carry the scope all produce a denial.
        """
        if self.token is None:
            decision = GateDecision(
                tool_name=tool_name,
                required_scope=required_scope,
                allowed=False,
                reason="No delegation token in force for this run.",
            )
            self.decisions.append(decision)
            self.requested_scopes.add(required_scope)
            return decision

        task_id = self.token.task.id
        root = self.token.chain.root_principal.principal_id

        if self.token.expires_at <= datetime.now(timezone.utc):
            decision = GateDecision(
                tool_name=tool_name,
                required_scope=required_scope,
                allowed=False,
                reason="Delegation token has expired.",
                task_id=task_id,
                root_principal=root,
            )
            self.decisions.append(decision)
            return decision

        allowed = is_permitted(self.effective_scopes, required_scope)
        decision = GateDecision(
            tool_name=tool_name,
            required_scope=required_scope,
            allowed=allowed,
            reason=(
                f"Scope '{required_scope}' is carried by the delegation chain."
                if allowed
                else f"Scope '{required_scope}' was never delegated by {root}."
            ),
            task_id=task_id,
            root_principal=root,
        )
        self.decisions.append(decision)
        if not allowed:
            self.requested_scopes.add(required_scope)
        return decision


_current_delegation: ContextVar[DelegationContext] = ContextVar(
    "gl_iam_delegation_context",
    default=DelegationContext(),
)


def set_delegation_context(context: DelegationContext) -> Any:
    """Install the delegation context for the current run.

    Returns the ContextVar token so the caller can reset it afterwards.
    """
    return _current_delegation.set(context)


def reset_delegation_context(token: Any) -> None:
    """Restore the delegation context that was in force before the run."""
    _current_delegation.reset(token)


def get_delegation_context() -> DelegationContext:
    """Read the delegation context in force for the current run."""
    return _current_delegation.get()


def get_required_scope(tool: Any) -> str | None:
    """Return the scope a tool declares, or ``None`` if it is ungated."""
    return getattr(tool, REQUIRED_SCOPE_ATTR, None)


T = TypeVar("T", bound=type)


def requires_scope(scope: str) -> Callable[[T], T]:
    """Declare the scope a tool needs, and enforce it at call time.

    Wraps the tool's ``_run`` and ``_arun`` so neither can execute unless the
    delegation token in force carries ``scope``. On denial the tool returns a
    structured refusal instead of raising: the agent sees why it was blocked
    and can degrade gracefully (skip the step, tell the user) rather than
    crashing the whole run.

    Args:
        scope: The scope this tool requires, in GL-IAM's ``resource:action``
            convention (e.g. ``"google_docs:write"``).

    Returns:
        A class decorator that tags and guards the tool class.
    """

    def decorate(tool_cls: T) -> T:
        setattr(tool_cls, REQUIRED_SCOPE_ATTR, scope)

        def denial_payload(decision: GateDecision, tool_name: str) -> dict[str, Any]:
            return {
                "status": "permission_denied",
                "tool": tool_name,
                "required_scope": scope,
                "reason": decision.reason,
                "remediation": (
                    f"Ask the user to grant '{scope}' to this agent, then retry."
                ),
            }

        original_arun = getattr(tool_cls, "_arun", None)
        original_run = getattr(tool_cls, "_run", None)

        if original_arun is not None:

            @functools.wraps(original_arun)
            async def guarded_arun(self: Any, *args: Any, **kwargs: Any) -> Any:
                decision = get_delegation_context().check(self.name, scope)
                if not decision.allowed:
                    return denial_payload(decision, self.name)
                return await original_arun(self, *args, **kwargs)

            tool_cls._arun = guarded_arun  # type: ignore[attr-defined]

        if original_run is not None:

            @functools.wraps(original_run)
            def guarded_run(self: Any, *args: Any, **kwargs: Any) -> Any:
                decision = get_delegation_context().check(self.name, scope)
                if not decision.allowed:
                    return denial_payload(decision, self.name)
                return original_run(self, *args, **kwargs)

            tool_cls._run = guarded_run  # type: ignore[attr-defined]

        return tool_cls

    return decorate


__all__ = [
    "DelegationContext",
    "GateDecision",
    "get_delegation_context",
    "get_required_scope",
    "requires_scope",
    "reset_delegation_context",
    "set_delegation_context",
]
