"""Custom host-boundary experiments for the AGT/ACS exploration.

This harness deliberately replaces the native module with a no-op module and
drives the upstream Python orchestration API with a small RuntimeClient. It is
evidence about host/application ownership, not the native policy evaluator.
The native path is validated separately by ``run_official_demo.ps1``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import types
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("AGT_REPO", ROOT / "upstream" / "agent-governance-toolkit"))
SDK = REPO / "policy-engine" / "sdk" / "python"
EMAIL_EXAMPLE = ROOT / "examples" / "acs-email-tool"

if not SDK.is_dir() or not EMAIL_EXAMPLE.is_dir():
    raise SystemExit("The AGT SDK or curated email example was not found. Run setup_demo.ps1 from this exploration.")

sys.path.insert(0, str(SDK))
sys.path.insert(0, str(EMAIL_EXAMPLE))

# The source imports its compiled extension while loading validation helpers.
# These boundary experiments use no native entry point, so a no-op module keeps
# that dependency explicitly outside this custom harness.
sys.modules["agent_control_specification._native"] = types.ModuleType(
    "agent_control_specification._native"
)

from agent_control_specification import (  # noqa: E402
    AgentControl,
    AgentControlBlocked,
    AgentControlSuspended,
    ApprovalResolution,
    InterventionPoint,
    InterventionPointRequest,
    InterventionPointResult,
    Verdict,
    action_identity,
)
from email_policy import EmailPolicy  # noqa: E402


def emit(event: str, **data: Any) -> None:
    print(json.dumps({"event": event, **data}, sort_keys=True))


def policy_input(request: InterventionPointRequest) -> dict[str, Any]:
    point = (
        request.intervention_point.value
        if isinstance(request.intervention_point, InterventionPoint)
        else str(request.intervention_point)
    )
    snapshot = dict(request.snapshot)
    target: Any = snapshot
    if point == InterventionPoint.PRE_TOOL_CALL.value:
        target = snapshot.get("tool_call", {}).get("args")
    elif point == InterventionPoint.POST_TOOL_CALL.value:
        target = snapshot.get("tool_result")
    return {
        "intervention_point": point,
        "snapshot": snapshot,
        "policy_target": {"value": target},
    }


class HarnessRuntime:
    """Minimal custom RuntimeClient used to exercise upstream host orchestration."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.email_policy = EmailPolicy()

    async def evaluate_intervention_point(
        self, request: InterventionPointRequest
    ) -> InterventionPointResult:
        payload = policy_input(request)
        point = payload["intervention_point"]

        if point == InterventionPoint.POST_TOOL_CALL.value:
            mapping: dict[str, Any] = {"decision": "allow"}
        elif self.mode == "email":
            mapping = dict(self.email_policy.evaluate({"input": payload}))
        elif self.mode == "approval":
            mapping = {
                "decision": "deny",
                "reason": "approval_required",
                "message": "Host approval is required.",
                "approval": {"kind": "human", "timeout_seconds": 300},
            }
        elif self.mode == "missing":
            mapping = {
                "decision": "deny",
                "reason": "runtime_error:policy_not_configured",
                "message": "No policy was configured by the host.",
            }
        elif self.mode == "raise":
            raise RuntimeError("[CUSTOM HARNESS] evaluator crashed")
        else:
            raise ValueError(f"unknown harness mode: {self.mode}")

        verdict = Verdict.from_mapping(mapping)
        identity = action_identity(payload)
        return InterventionPointResult(
            verdict=verdict,
            policy_input=payload,
            input_identity=identity,
            enforced_identity=identity,
        )


class FakeEmailTool:
    """Harmless stand-in side effect with visible execution."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def __call__(self, args: dict[str, str]) -> dict[str, Any]:
        self.calls.append(dict(args))
        emit("fake_tool_executed", args=args, call_count=len(self.calls))
        return {"sent": True, **args}


async def experiment_allow() -> None:
    tool = FakeEmailTool()
    control = AgentControl(HarnessRuntime("email"))
    args = {"to": "customer@example.com", "body": "Status update"}
    result = await control.run_tool("send_email", args, tool, tool_call_id="allow-1")
    emit(
        "experiment_result",
        experiment="01_allow",
        decision=result.pre_tool_call_result.verdict.decision.value,
        executed=len(tool.calls) == 1,
        output=result.value,
    )


async def experiment_deny() -> None:
    tool = FakeEmailTool()
    control = AgentControl(HarnessRuntime("email"))
    args = {"to": "partner@example.net", "body": "Status update"}
    try:
        await control.run_tool("send_email", args, tool, tool_call_id="deny-1")
    except AgentControlBlocked as exc:
        emit(
            "experiment_result",
            experiment="02_deny",
            decision=exc.result.verdict.decision.value,
            reason=exc.result.verdict.reason,
            executed=bool(tool.calls),
            exception=type(exc).__name__,
        )


async def experiment_approval() -> None:
    async def approve(_point: InterventionPoint, result: InterventionPointResult):
        emit("approval_resolver", outcome="allow", action_identity=result.action_identity)
        return ApprovalResolution.allow(result.action_identity or "")

    async def reject(_point: InterventionPoint, result: InterventionPointResult):
        emit("approval_resolver", outcome="deny", action_identity=result.action_identity)
        return ApprovalResolution.deny()

    async def suspend(_point: InterventionPoint, result: InterventionPointResult):
        emit("approval_resolver", outcome="suspend", action_identity=result.action_identity)
        return ApprovalResolution.suspend(
            {"ticket": "approval-demo-1"}, result.action_identity
        )

    args = {"to": "customer@example.com", "body": "Needs approval"}
    outcomes = []
    for label, resolver in (("approve", approve), ("reject", reject), ("suspend", suspend)):
        tool = FakeEmailTool()
        control = AgentControl(HarnessRuntime("approval"), approval_resolver=resolver)
        try:
            result = await control.run_tool(
                "send_email", args, tool, tool_call_id=f"approval-{label}"
            )
            outcomes.append(
                {
                    "case": label,
                    "result": "executed",
                    "executed": bool(tool.calls),
                    "output": result.value,
                }
            )
        except AgentControlSuspended as exc:
            outcomes.append(
                {
                    "case": label,
                    "result": "suspended",
                    "executed": bool(tool.calls),
                    "handle": exc.handle,
                }
            )
        except AgentControlBlocked as exc:
            outcomes.append(
                {
                    "case": label,
                    "result": "blocked",
                    "executed": bool(tool.calls),
                    "reason": exc.result.verdict.reason,
                }
            )
    emit("experiment_result", experiment="03_approval", outcomes=outcomes)


async def experiment_failure() -> None:
    outcomes = []
    for mode in ("missing", "raise"):
        tool = FakeEmailTool()
        control = AgentControl(HarnessRuntime(mode))
        try:
            await control.run_tool(
                "send_email",
                {"to": "customer@example.com", "body": "Failure case"},
                tool,
                tool_call_id=f"failure-{mode}",
            )
        except AgentControlBlocked as exc:
            outcomes.append(
                {
                    "case": mode,
                    "result": "blocked",
                    "reason": exc.result.verdict.reason,
                    "executed": bool(tool.calls),
                }
            )
        except Exception as exc:
            outcomes.append(
                {
                    "case": mode,
                    "result": "exception_propagated",
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "executed": bool(tool.calls),
                }
            )
    emit("experiment_result", experiment="04_failure", outcomes=outcomes)


async def restart_create() -> None:
    async def suspend(_point: InterventionPoint, result: InterventionPointResult):
        return ApprovalResolution.suspend(
            {"ticket": "pending-before-restart"}, result.action_identity
        )

    tool = FakeEmailTool()
    control = AgentControl(HarnessRuntime("approval"), approval_resolver=suspend)
    try:
        await control.run_tool(
            "send_email",
            {"to": "customer@example.com", "body": "Pending"},
            tool,
            tool_call_id="restart-1",
        )
    except AgentControlSuspended as exc:
        emit(
            "experiment_result",
            experiment="05_restart_create",
            state="pending_only_in_exception_handle",
            handle=exc.handle,
            executed=bool(tool.calls),
            persisted_by_sdk=False,
        )


async def restart_inspect() -> None:
    emit(
        "experiment_result",
        experiment="05_restart_inspect",
        state="no_pending_state_loaded",
        persisted_by_sdk=False,
        resumable_by_sdk=False,
        explanation=(
            "A new process constructs a new AgentControl; the SDK exposes no "
            "approval store or resume method."
        ),
    )


async def experiment_reuse_changed_args() -> None:
    approved_identity: str | None = None

    async def resolver(_point: InterventionPoint, result: InterventionPointResult):
        nonlocal approved_identity
        if approved_identity is None:
            approved_identity = result.action_identity
            emit("approval_saved_in_host_memory", action_identity=approved_identity)
        return ApprovalResolution.allow(approved_identity or "")

    control = AgentControl(HarnessRuntime("approval"), approval_resolver=resolver)
    tool = FakeEmailTool()
    args1 = {"to": "customer@example.com", "body": "Original"}
    args2 = {"to": "customer@example.com", "body": "Changed"}
    outcomes = []

    for label, args in (
        ("original", args1),
        ("same_args_reuse", args1),
        ("changed_args", args2),
    ):
        before = len(tool.calls)
        try:
            await control.run_tool(
                "send_email", args, tool, tool_call_id="stable-call-id"
            )
            outcomes.append(
                {
                    "case": label,
                    "result": "executed",
                    "new_calls": len(tool.calls) - before,
                }
            )
        except AgentControlBlocked as exc:
            outcomes.append(
                {
                    "case": label,
                    "result": "blocked",
                    "reason": exc.result.verdict.reason,
                    "new_calls": len(tool.calls) - before,
                }
            )

    emit(
        "experiment_result",
        experiment="06_reuse_changed_args",
        approved_identity=approved_identity,
        outcomes=outcomes,
    )


async def experiment_direct_bypass() -> None:
    governed_tool = FakeEmailTool()
    direct_tool = FakeEmailTool()
    args = {"to": "partner@example.net", "body": "Direct call"}
    control = AgentControl(HarnessRuntime("email"))
    governed = "unexpected"
    try:
        await control.run_tool("send_email", args, governed_tool, tool_call_id="bypass-1")
    except AgentControlBlocked:
        governed = "blocked"
    direct = await direct_tool(args)
    emit(
        "experiment_result",
        experiment="07_direct_bypass",
        governed_result=governed,
        governed_executions=len(governed_tool.calls),
        direct_result="executed",
        direct_executions=len(direct_tool.calls),
        direct_output=direct,
    )


async def run_named(name: str) -> None:
    experiments = {
        "01": experiment_allow,
        "02": experiment_deny,
        "03": experiment_approval,
        "04": experiment_failure,
        "05-create": restart_create,
        "05-inspect": restart_inspect,
        "06": experiment_reuse_changed_args,
        "07": experiment_direct_bypass,
    }
    await experiments[name]()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", choices=[
        "01", "02", "03", "04", "05-create", "05-inspect", "06", "07"
    ])
    args = parser.parse_args()
    asyncio.run(run_named(args.experiment))


if __name__ == "__main__":
    main()
