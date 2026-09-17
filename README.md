# Railproof

![Status: alpha](https://img.shields.io/badge/status-alpha-orange)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Apache-2.0 license](https://img.shields.io/badge/license-Apache--2.0-green)
[![PyPI](https://img.shields.io/pypi/v/railproof.svg)](https://pypi.org/project/railproof/)
[![PyPI downloads](https://img.shields.io/pypi/dm/railproof.svg)](https://pypi.org/project/railproof/)
![110 tests](https://img.shields.io/badge/tests-110%20passing-brightgreen)
![94.18% branch coverage](https://img.shields.io/badge/branch%20coverage-94.18%25-brightgreen)

## The short version

AI agents can now send emails, move money, call APIs, modify tickets, and touch production systems.

The problem is not whether the model can choose a tool. The problem is whether that exact action should be allowed.

Railproof puts a deterministic security contract in front of every tool call. It checks the tool, complete arguments, user, tenant, roles, data labels, provenance, approvals, and session budgets before application code runs.

If the action is not explicitly allowed, it does not execute.

## Why product teams need this

Most guardrails answer one of these questions:

- Is the request safe to discuss?
- Does the tool call match a JSON shape?
- Is this tool on an allowlist?

Those checks are useful, but they do not answer the business question:

> “Should this agent be allowed to perform this exact operation for this user, with this data, in this session, right now?”

A request can be perfectly valid JSON and still be wrong. It can send data to the wrong host, use retrieved content as an email recipient, exceed a spending budget, or reuse an approval after the action changes.

Railproof is the enforcement layer for that decision.

## What this repository covers

This repository contains the complete v0.1.0 alpha implementation:

| Area | What is included |
|---|---|
| Policy | A strict, versioned YAML policy language with deny-by-default behavior |
| Authorization | Deterministic rules over actions, users, tenants, roles, tools, sinks, labels, provenance, and session state |
| Execution | A wrapped tool registry that cannot run a tool call before the decision is made |
| Approvals | One-time HMAC approval tokens bound to the exact action, policy, principal, expiry, and nonce |
| Budgets | Atomic per-session call-count and numeric-sum limits |
| Evidence | Bounded redacted records with policy, action, and decision hashes |
| Integrations | Normalizers for OpenAI Chat Completions function calls and MCP `tools/call` requests |
| Testing | Adversarial, concurrency, property-based, replay, CLI, and integration tests |
| Operations | CLI validation, single-event checks, JSONL replay, locked builds, dependency audits, and CI |
| Benchmarking | A reproducible comparison against NeMo Guardrails 0.24.0’s built-in tool-call validator |

## What this means for a product owner

You define the rules once. Every connected agent and tool call goes through the same decision contract.

### 1. Stop actions that are technically valid but business-invalid

JSON Schema can confirm that an email has a `to` field and a `body`. Railproof can additionally say:

- never send sensitive data to an external sink
- never let retrieved content choose an email recipient
- only call a transfer tool within a session budget
- allow weather lookups but require approval for external email
- deny unknown tools and unmatched actions

The policy does not ask the model whether the action is safe. The model has no authority to override it.

### 2. Require approval for high-impact actions

A rule can stop an action and return an approval challenge. The approval is cryptographically bound to the exact action.

Change the recipient, amount, tool, user, or policy and the old approval no longer works. Reuse the same approval and it is rejected.

The v0.1.0 broker is the security primitive, not a finished approval dashboard or human workflow. Your product can connect it to the approval system you already use.

### 3. Enforce budgets across a session

Policies can limit:

- how many times a tool is called
- how much numeric value accumulates across calls
- per-session budgets that can be applied alongside user and tenant rules

The reservation happens before execution and is atomic for concurrent calls. A burst of parallel requests cannot spend the same remaining budget twice.

### 4. Keep a useful decision trail

Railproof records whether a call was allowed, denied, waiting for approval, started, completed, or failed.

Built-in evidence includes identifiers, hashes, matched rules, reasons, outcomes, and a hashed principal. It does not store raw arguments, approval tokens, prompts, or tool results.

Use the in-memory sink for local work or the append-only JSONL sink for a file-based audit trail.

### 5. Give different agent stacks the same security contract

The policy engine is protocol-independent. The repository includes adapters that normalize:

- OpenAI Chat Completions function calls
- MCP JSON-RPC 2.0 `tools/call` requests

Both become the same canonical event before policy evaluation.

### 6. Test policy behavior before production

The CLI can validate policies, evaluate one event, and replay JSONL decision fixtures. That gives product and security teams a way to review expected outcomes without making real tool calls.

The repository also includes a benchmark and its raw result. Railproof scored 10/10 against the benchmark’s declared requirements. NeMo Guardrails 0.24.0’s built-in tool-call validator scored 5/10.

That is a narrow comparison against one NeMo rail. It is not a claim that Railproof replaces NeMo’s conversational rails, model-backed detectors, server, or observability.

## How a decision works

```text
Agent proposes a tool call
          |
          v
Adapter or GuardedTools creates one canonical action snapshot
          |
          v
Policy validates tool, arguments, identity, labels, provenance, and session limits
          |
       +--+-------------------+
       |                      |
     deny             allow or approval
       |                      |
   no execution       reserve limits and verify approval
                              |
                              v
                    wrapped executor runs exact snapshot
                              |
                              v
                    evidence records the outcome
```

The important boundary is simple: application code does not receive a tool result until the action has passed the contract.

## Feature detail

### Strict policy compiler

Policies use the `railproof.dev/v1alpha1` format. Compilation fails closed when the policy contains:

- unknown fields or duplicate keys
- an unsafe default
- undeclared tools or limits
- unsupported stages, effects, operators, or fields
- invalid JSON Schema
- schema references not supported by this alpha
- oversized policy input or excessive YAML aliases

Every compiled policy receives a deterministic SHA-256 policy hash.

### Deterministic authorization

The decision engine evaluates locally with no model call and no network call. It supports:

- equality and inequality
- membership and exclusion
- numeric upper and lower bounds
- field labels such as `sensitive`
- provenance such as `retrieved.email`
- principal ID, tenant, and roles
- tool risk and sink metadata
- per-session call counts and numeric sums

Decision precedence is fixed:

```text
deny > require approval > allow > unmatched deny
```

There is no implicit allow.

### Exact-action binding

Railproof canonicalizes the caller’s arguments once into isolated event and execution snapshots. The hash covers:

- policy
- session
- principal identity, tenant, and roles
- tool name
- complete arguments
- labels
- provenance

This prevents a mutable or stateful caller mapping from being authorized as one action and executed as another.

### Approval tokens

The built-in approval broker uses HMAC-SHA-256 and requires a signing key of at least 32 bytes. Tokens bind the action hash, policy hash, principal, approver, expiry, and random nonce.

It rejects forged, modified, malformed, expired, cross-principal, and reused tokens. Token replay protection is process-local in v0.1.0.

### Safe execution wrapper

`GuardedTools` combines authorization and execution so application code does not need to remember a separate “check first, execute later” rule.

It supports synchronous and asynchronous executors, prevents denied executor entry, reserves budgets atomically, bounds active session state, and refuses session teardown while an execution is in flight.

### Evidence sinks

Two sinks are included:

- `InMemoryEvidenceSink` with bounded retention, defaulting to 10,000 records
- `JsonlEvidenceSink` for append-only newline-delimited records

The built-in record contains event/session/tool identifiers, a principal hash, action/policy/decision hashes, outcome, matched rules, and reason codes.

### CLI and replay

```bash
railproof validate policy.yaml
railproof check policy.yaml event.json
railproof replay policy.yaml fixtures.jsonl
```

`validate` compiles a policy and prints its hash. `check` evaluates one event. `replay` compares actual outcomes with expected outcomes and returns a failing exit code when fixtures disagree.

## Install

Railproof is published on [PyPI](https://pypi.org/project/railproof/). Install the latest release with:

```bash
python -m pip install railproof
```

Or with uv:

```bash
uv add railproof
```

Package links:

- [PyPI project page](https://pypi.org/project/railproof/)
- [PyPI release files](https://pypi.org/project/railproof/#files)
- [GitHub releases](https://github.com/ppradyoth/railproof/releases)

The package includes the runtime library and the `railproof` command. No repository clone is needed to use it.

## Quick start from source

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ppradyoth/railproof.git
cd railproof
uv sync --group dev --group test
uv run railproof validate examples/policy.yaml
uv run python examples/demo.py
```

The demo shows a benign weather call, a denied sensitive email, an approval challenge, and an approved email.

## Add it to an application

Register the real executor once, then route calls through `GuardedTools`:

```python
from railproof.executor import GuardedTools, ToolRegistry
from railproof.models import Principal
from railproof.policy import load_policy

policy = load_policy("policy.yaml")
registry = ToolRegistry()
registry.register("get_weather", get_weather)

tools = GuardedTools(policy, registry)
result = await tools.call(
    "get_weather",
    {"city": "Bengaluru"},
    principal=Principal(id="user-123", tenant="tenant-a"),
    session_id="session-123",
)
```

For high-impact actions, configure an `ApprovalBroker`, catch `ApprovalRequired`, obtain approval through your application workflow, and call the same action with the returned token.

See the [complete example policy](examples/policy.yaml) and [runnable demo](examples/demo.py).

## What Railproof is not

This alpha is an enforcement runtime, not a complete AI platform. It does not provide:

- a model or content-moderation system
- a sandbox against code that bypasses the wrapper
- automatic taint tracking or provenance attestation
- tool-result validation after execution
- argument rewriting or policy-driven mutation
- persistent or distributed session budgets and nonce storage
- a hosted control plane, dashboard, or approval UI
- a TypeScript SDK

These are explicit boundaries. Production teams should keep the underlying executors private, default policies to deny, protect signing keys, and treat labels and provenance as application-attested inputs.

## Evidence for the v0.1.0 alpha

| Gate | Result |
|---|---:|
| Tests | 110 passed |
| Branch coverage | 94.18% |
| NeMo comparison | Railproof 10/10, NeMo 5/10 |
| Railproof benchmark latency | 44 µs p50, 48 µs p95, 57 µs p99 |
| NeMo benchmark latency | 492 µs p50, 517 µs p95, 575 µs p99 |
| Dependency audit | No known vulnerabilities found |
| GitHub Actions workflow audit | Zizmor: no findings |

The benchmark uses NeMo Guardrails 0.24.0’s real deterministic `ToolCallRailAction._validate` implementation with no model or network calls. Read the [benchmark method](docs/BENCHMARK.md) before interpreting the comparison.

## Repository map

| Path | Purpose |
|---|---|
| `src/railproof/` | Runtime, policy compiler, engine, approvals, evidence, adapters, CLI, and replay |
| `tests/` | Security and correctness contract tests |
| `examples/` | Copy-pasteable policy and runnable demo |
| `benchmarks/` | NeMo comparison harness and benchmark policy |
| `docs/` | Architecture, product specification, threat model, competitive analysis, and benchmark evidence |
| `PROJECT_PLAN.md` | Product direction and staged roadmap |
| `.github/workflows/ci.yml` | Python quality matrix, dependency audit, and benchmark gate |
| `.github/workflows/publish.yml` | Tag-triggered, OIDC-based PyPI publishing |

## Development

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check src tests examples
uv run pytest -q
uv run pip-audit
uv build
```

Read [SECURITY.md](SECURITY.md) before production use. Contributions should include an adversarial fixture, a benign control, an expected decision, and proof of whether the executor was reached. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Product specification](docs/PRODUCT_SPEC.md)
- [Threat model](docs/THREAT_MODEL.md)
- [NeMo comparison](docs/COMPETITIVE_ANALYSIS.md)
- [Benchmark method](docs/BENCHMARK.md)
- [Project plan](PROJECT_PLAN.md)
- [Roadmap](ROADMAP.md)

Apache-2.0 licensed.
