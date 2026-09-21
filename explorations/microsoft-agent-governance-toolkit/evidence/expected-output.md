# Recorded output and interpretation

This file captures the expected shape of the exploration output. Timing,
action-identity hashes, and dependency download messages can differ between
machines.

## Dependency check

`test_policy_engine_sdk.ps1` only validates that the native ACS extension
imports and that the SDK's own test suite passes:

```text
253 passed, 34 skipped, 1 deselected, 52 subtests passed
```

The deselected test uses `/bin/true` as a non-OPA executable and is POSIX
specific. This script does not run any example.

## Upstream path

The recorded Windows run of `run_upstream_example.ps1` (Microsoft's
unmodified `examples/acs-email-tool`, run straight from the pinned clone)
completed with:

```text
5 passed
[allow] decision=allow sent=True body=Your case is ready.
[transform] decision=transform sent=True body=Your case is ready. Tracking token: [REDACTED]
[deny] decision=deny executed=False reason=external_recipient_blocked
```

The example calls a fake email function; it sends no network email. This
path uses `HostSession.pre_tool_call()` only, so `post_tool_call` is never
exercised here.

## Official logging path

`run_official_logging.ps1` reproduces the same three outcomes (allow,
transform, deny) through the harness (`harness/run_experiments.py`,
experiments `01`, `01-transform`, `02`), using `AgentControl.run_tool()`
instead of `HostSession`. The console presents a readable, ordered flow for
each case: the relevant ACS snapshot, policy evaluation, decision,
enforcement, and final result — including the `post_tool_call` pass that
`run_upstream_example.ps1` does not perform. Raw machine-readable events are
written as JSON Lines to the ignored
`evidence/runtime-output/official-logging.jsonl` file, replaced on each run.

| ID | Expected observation | Interpretation |
| --- | --- | --- |
| 01 | Allowed call executes once. | Governed host path can permit execution. |
| 01-transform | `TRACK-123` is changed to `[REDACTED]` before the fake tool executes. | The host applies a pre-tool transform to the tool arguments. |
| 02 | Denied call executes zero times. | Denial blocks the wrapped fake tool. |

## Boundary logging path

`run_boundary_logging.ps1` runs the remaining, application/host-responsibility
experiments through the same harness. Raw machine-readable events are written
to the ignored `evidence/runtime-output/boundary-logging.jsonl` file, replaced
on each run.

| ID | Expected observation | Interpretation |
| --- | --- | --- |
| 03 | Approval resolver can allow, deny, or suspend. | Approval resolution is supplied by the host application. |
| 04 | Missing policy fails closed; a custom runtime exception propagates. | Failure handling depends on both SDK behavior and the host boundary. |
| 05 | A suspended handle exists in the first process; a new process loads no pending state. | The examined SDK path provides no durable approval store or resume workflow. |
| 06 | Same arguments reuse the stored approval identity; changed arguments are blocked. | Approval must remain bound to the action identity. |
| 07 | Governed call is blocked while a direct call executes. | Calls outside the wrapper bypass this governance path. |

Both harness scripts intentionally substitute a small custom runtime for the
native evaluator. They use upstream ACS host orchestration types but must not
be cited as proof of native policy evaluation — that evidence comes from
`test_policy_engine_sdk.ps1` and `run_upstream_example.ps1` instead. Because
both harness scripts call `run_tool()`, every case in either one traverses
`post_tool_call` after successful execution, but the harness's post-tool
policy is an unconditional `allow`; it does not demonstrate output-sensitive
post-tool transformation or blocking.

## Evidence classification

- **Runtime-observed:** native extension import, selected SDK test result,
  official email behavior, and custom boundary outputs.
- **Source-inspected:** component ownership, intervention-point implementation,
  dashboard data generation, and broader package inventory.
- **Mapped/documented:** standards and compliance-control mappings.
- **Not established:** production integration, live dashboard backend,
  persistent operational approval service, complete audit export, or external
  compliance certification.
