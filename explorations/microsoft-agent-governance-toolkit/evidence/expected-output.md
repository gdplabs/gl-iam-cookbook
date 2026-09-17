# Recorded output and interpretation

This file captures the expected shape of the exploration output. Timing,
action-identity hashes, and dependency download messages can differ between
machines.

## Official path

The recorded Windows run of `run_official_demo.ps1` completed with:

```text
253 passed, 34 skipped, 1 deselected, 52 subtests passed
5 passed
[allow] decision=allow sent=True body=Your case is ready.
[transform] decision=transform sent=True body=Your case is ready. Tracking token: [REDACTED]
[deny] decision=deny executed=False reason=external_recipient_blocked
```

The deselected test uses `/bin/true` as a non-OPA executable and is POSIX
specific. The official example calls a fake email function; it sends no network
email.

## Custom boundary path

`run_boundary_demo.ps1` runs these experiments:

| ID | Expected observation | Interpretation |
| --- | --- | --- |
| 01 | Allowed call executes once. | Governed host path can permit execution. |
| 02 | Denied call executes zero times. | Denial blocks the wrapped fake tool. |
| 03 | Approval resolver can allow, deny, or suspend. | Approval resolution is supplied by the host application. |
| 04 | Missing policy fails closed; a custom runtime exception propagates. | Failure handling depends on both SDK behavior and the host boundary. |
| 05 | A suspended handle exists in the first process; a new process loads no pending state. | The examined SDK path provides no durable approval store or resume workflow. |
| 06 | Same arguments reuse the stored approval identity; changed arguments are blocked. | Approval must remain bound to the action identity. |
| 07 | Governed call is blocked while a direct call executes. | Calls outside the wrapper bypass this governance path. |

The boundary harness intentionally substitutes a small custom runtime for the
native evaluator. It uses upstream ACS host orchestration types but must not be
cited as proof of native policy evaluation. Its `run_tool()` calls traverse
`post_tool_call` after successful execution, but the harness returns an
unconditional `allow` at that point; it does not demonstrate output-sensitive
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
