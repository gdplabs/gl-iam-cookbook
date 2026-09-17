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
| OPA / Rego | The SDK validation path exercised policy artifact validation with a local OPA executable. | The official email example itself uses a custom Python policy, not Rego for its allow/transform/deny decisions. |
| Dashboard | The reference Streamlit dashboard uses generated demo data. | It is not a live feed from the email example or the boundary harness. |

## Included files

```text
microsoft-agent-governance-toolkit/
├── README.md
├── setup_demo.ps1             # clone/pin AGT and build the native Python extension
├── run_official_demo.ps1      # selected SDK validation + official email example
├── run_boundary_demo.ps1      # run the seven custom host-boundary experiments
├── harness/
│   └── run_experiments.py     # exploration-owned custom runtime and fake tool
└── evidence/
    └── expected-output.md      # recorded output shape and interpretation
```

The scripts download the upstream source into the ignored `upstream/` folder
and create an ignored `.venv/`. Neither generated directory is committed.

## Upstream source map

All links below are pinned to the explored commit.

| Concern | Upstream source |
| --- | --- |
| Official host flow and enforcement | [`examples/acs-email-tool/run.py`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/examples/acs-email-tool/run.py#L27-L82) |
| Custom email policy and transform | [`examples/acs-email-tool/email_policy.py`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/examples/acs-email-tool/email_policy.py#L10-L42) |
| Email policy manifest | [`examples/acs-email-tool/manifest.yaml`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/examples/acs-email-tool/manifest.yaml) |
| High-level `run_tool` pre/post flow | [`policy-engine/sdk/python/agent_control_specification/_orchestration.py`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/policy-engine/sdk/python/agent_control_specification/_orchestration.py#L284-L328) |
| Lower-level `HostSession` intervention methods | [`policy-engine/sdk/python/agent_control_specification/_host.py`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/policy-engine/sdk/python/agent_control_specification/_host.py#L371-L398) |
| Post-tool PII example | [`policy-engine/examples/support_agent/manifest.yaml`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/policy-engine/examples/support_agent/manifest.yaml#L32-L38) and [`customer_support_guardrails.rego`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/policy-engine/examples/support_agent/policy/customer_support_guardrails.rego#L71-L80) |
| Generated dashboard data | [`examples/demos/governance-dashboard/app.py`](https://github.com/microsoft/agent-governance-toolkit/blob/1a896e70aca8ced2a243d5702cb0359d4ded5c50/examples/demos/governance-dashboard/app.py#L7-L14) |

## Key finding: where enforcement occurs

The official email sample uses the lower-level `HostSession` flow. Before a
tool invocation, the host calls `pre_tool_call`, inspects the decision, applies
any transformed arguments, and invokes the tool only when the decision permits
it. Therefore, application coverage matters: a direct tool call that does not
pass through the governed host path is not automatically controlled.

The official email demonstration proves **pre-execution** policy enforcement.
It does not explicitly evaluate the completed result through `post_tool_call`;
`record_tool_call()` records session context and is not a post-tool policy
evaluation. The custom boundary harness uses the higher-level `run_tool()` API,
so allowed executions also pass through `post_tool_call`, but its custom
post-tool policy is an unconditional `allow`. It therefore verifies the
orchestration path, not content-based post-tool redaction or denial. Those
controls are useful when a result must be checked, changed, or withheld before
reaching an agent or user. For example, the upstream
`policy-engine/examples/support_agent` source configures post-tool policy for
PII in a tool result.

## Reproduction baseline

The original AGT repository and generated build artifacts are intentionally not
vendored here. Windows prerequisites are Git, Python 3.11 with the `py`
launcher, Rustup/MSVC build tools, and OPA. Put `opa.exe` on `PATH`, or set
`OPA_EXE` to its absolute path. OPA 1.20.2 was used in the recorded run.

From this folder, run:

```powershell
.\setup_demo.ps1
.\run_official_demo.ps1
.\run_boundary_demo.ps1
```

`setup_demo.ps1` clones the Microsoft repository, checks out the pinned commit,
creates `.venv`, selects Rust 1.89 MSVC, and builds the ACS extension with
Maturin 1.8.7. `run_official_demo.ps1` runs the selected native SDK validation
and the upstream email example. `run_boundary_demo.ps1` runs the
exploration-owned custom harness. See
[`evidence/expected-output.md`](evidence/expected-output.md) for the expected
result shape and the correct evidence interpretation.

The setup script enables Git long-path support for its local AGT checkout. If
Windows still rejects a checkout because of a path-length policy, enable
long-path support in Windows or clone the cookbook into a shorter directory.

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
