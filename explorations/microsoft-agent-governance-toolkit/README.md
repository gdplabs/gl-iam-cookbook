# Microsoft Agent Governance Toolkit (AGT) Exploration

This folder records a scoped technical exploration of the [Microsoft Agent
Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
(AGT). It is **not** a GL-IAM integration example, adoption recommendation, or
compliance certification. It is retained in the cookbook as a reproducible
research reference for policy enforcement around agent tool calls.

The explored checkout was pinned to commit
[`1a896e70aca8ced2a243d5702cb0359d4ded5c50`](https://github.com/microsoft/agent-governance-toolkit/tree/1a896e70aca8ced2a243d5702cb0359d4ded5c50).

## Scope

The exploration focused on the Agent Control Specification (ACS) Python path:

```text
AGT policy-engine
  Rust native runtime
       ↓  (Maturin build)
  ACS Python SDK
       ↓
official acs-email-tool example
```

It examined policy configuration, evaluation before a tool call, enforcement,
approval boundaries, persistence/restart responsibility, direct-call bypass,
and the reference governance dashboard. The broader
`agent-governance-python` package family was inventoried from source but was
not run as one complete runtime stack.

## Evidence summary

| Area | What was established | Evidence boundary |
| --- | --- | --- |
| Native ACS path | The Rust-backed ACS Python extension built and imported on Windows with Python 3.11, Rust 1.89 MSVC, and Maturin 1.8.7. | Runtime-tested locally. |
| SDK validation | The selected Windows test command completed with 253 passed, 34 skipped, 1 deselected, and 52 subtests passed. | The deselected test expects the POSIX executable `/bin/true`; this is not a claim that every cross-platform test passed. |
| Official email example | A governed fake email tool was allowed, transformed, or denied. Transform redacted a tracking token before the fake tool executed; deny prevented execution. | Runtime-tested locally; no real email was sent. |
| Approval and restart | Approval resolution, pending-state restart, changed-argument reuse, and direct bypass were explored through a custom harness. | The harness examines host/application responsibility; it is not an official AGT sample and does not prove native evaluator behavior. |
| OPA / Rego | The SDK validation path exercised policy artifact validation with the bundled OPA executable. | The official email example itself uses a custom Python policy, not Rego for its allow/transform/deny decisions. |
| Dashboard | The reference Streamlit dashboard uses generated demo data. | It is not a live feed from the email example or the boundary harness. |

## Key finding: where enforcement occurs

The official email sample uses the lower-level `HostSession` flow. Before a
tool invocation, the host calls `pre_tool_call`, inspects the decision, applies
any transformed arguments, and invokes the tool only when the decision permits
it. Therefore, application coverage matters: a direct tool call that does not
pass through the governed host path is not automatically controlled.

The examined email and boundary demonstrations prove **pre-execution** policy
enforcement. They do not explicitly evaluate a completed tool result through
`post_tool_call`; `record_tool_call()` records session context and is not a
post-tool policy evaluation. AGT also supports `post_tool_call`, which is useful
when a tool result must be checked, redacted, or withheld before reaching an
agent or user. For example, the upstream `policy-engine/examples/support_agent`
source configures post-tool policy for PII in a tool result.

## Reproduction baseline

The original AGT repository and generated build artifacts are intentionally not
vendored here. To reproduce the investigated official path on Windows:

1. Clone AGT and check out the pinned commit above.
2. Install Python 3.11, the Rust 1.89 MSVC toolchain, Maturin 1.8.7, and an OPA
   executable on `PATH` (OPA 1.20.2 was used in the recorded run).
3. In `policy-engine`, set the local Rust override to
   `1.89.0-x86_64-pc-windows-msvc`.
4. In `policy-engine/sdk/python`, run `maturin develop --release` from the
   active Python environment.
5. Run the selected SDK tests:

   ```powershell
   python -m pytest -q tests -k "not rejects_non_opa_executable" -p no:cacheprovider
   ```

6. In `examples/acs-email-tool`, run its tests and `python run.py`.

The result should be interpreted as an exploration baseline, not a production
deployment recipe.

## Compliance mapping

The accompanying report maps AGT capabilities to OWASP Agentic Top 10, NIST AI
RMF, EU AI Act, SOC 2, AARM, and ATF requirements. Those mappings distinguish
runtime observations from source inspection and documentation claims. They do
not establish that a deployment is certified or automatically compliant; an
application still owns complete tool coverage, identity integration, durable
approval state, operational audit retention, and its own governance controls.

## Relationship to GL-IAM

AGT/ACS is a policy-governance toolkit; GL-IAM is an identity and authorization
SDK. They address complementary layers, but this exploration does not implement
or recommend an integration between them. Any future integration should be a
separate, explicitly scoped cookbook example with its own source, tests, and
security review.
