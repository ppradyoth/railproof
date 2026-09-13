# Railproof

Verifiable security contracts for AI agent actions.

Railproof is a fail-closed policy engine and wrapped tool executor. It authorizes the exact tool, arguments, principal, labels, provenance, approval, and session budget before application code runs.

## Why it exists

Model guardrails and JSON Schema validation answer useful questions, but not the whole authorization question. A schema-valid request can still send data to the wrong host, let retrieved content choose an email recipient, exceed a session budget, or reuse an approval for a modified action.

Railproof v0.1.0 adds those controls without an LLM call:

- strict, versioned YAML policy that rejects unknown fields and unsafe defaults
- deterministic deny-over-approval-over-allow decisions
- JSON Schema Draft 2020-12 argument validation
- semantic rules over arguments, principals, tool risk, sinks, labels, provenance, and state
- HMAC-signed approvals bound to one action, policy, principal, expiry, and nonce
- atomic per-session count and sum limits
- bounded in-memory session state to prevent unbounded attacker-controlled growth
- a wrapped registry that couples authorization to execution
- bounded redacted evidence with policy, action, and decision hashes
- OpenAI Chat Completions and MCP `tools/call` event adapters
- offline JSONL replay and a CLI

## Run it

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ppradyoth/railproof.git
cd railproof
uv sync --group dev --group test
uv run railproof validate examples/policy.yaml
uv run python examples/demo.py
```

Expected demo:

```text
Sunny in Bengaluru
Denied: sensitive_data_to_external_sink
Approval required for action <hash prefix>
Sent to review@example.com
```

Use the enforcement API around the only reference to each underlying tool:

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

See [the complete policy](examples/policy.yaml) and [runnable demo](examples/demo.py).

## Measured NeMo comparison

On the checked-in model-free tool authorization benchmark, Railproof v0.1.0 passed 10/10 scenarios and NeMo Guardrails v0.24.0's built-in tool-call validator passed 5/10.

| Property | Railproof | NeMo 0.24.0 built-in tool-call rail |
|---|---:|---:|
| Unknown tool and invalid schema | 2/2 | 2/2 |
| Benign controls | 3/3 | 3/3 |
| Destination policy | 1/1 | 0/1 |
| Provenance-aware recipient policy | 1/1 | 0/1 |
| Sensitive-flow policy | 1/1 | 0/1 |
| Action approval requirement | 1/1 | 0/1 |
| Cross-step budget | 1/1 | 0/1 |
| Total | **10/10** | **5/10** |

The same 10,000-iteration run measured 44 µs p50 and 57 µs p99 for Railproof, versus 492 µs p50 and 575 µs p99 for NeMo's validator on macOS arm64 with Python 3.11. This is a narrow win over NeMo's built-in deterministic tool-call rail, not a claim that Railproof replaces NeMo's conversational rails, model-backed detectors, server, or observability. NeMo can add semantic checks through custom actions.

Reproduce it:

```bash
uv sync --group benchmark
uv run python benchmarks/compare_nemo.py --iterations 10000
```

The [benchmark method](docs/BENCHMARK.md), [policy](benchmarks/policy.yaml), [runner](benchmarks/compare_nemo.py), and [raw result](docs/benchmark-results/v0.1.0-nemo-0.24.0.json) are checked in.

## Security boundary

Railproof controls only calls routed through `GuardedTools`. Direct access to an underlying executor bypasses it. Labels and provenance are application-attested inputs; v0.1.0 does not infer or cryptographically verify data lineage. Session state and approval replay protection are in-memory and process-local.

This alpha provides one enforcement stage, `before_tool`. It does not provide content moderation, a hosted service, distributed state, argument rewriting, or tool-result validation.

Read [SECURITY.md](SECURITY.md) before production use.

## Development

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check src tests examples
uv run pytest -q
uv run pip-audit
uv build
```

The test suite contains 110 deterministic, adversarial, concurrency, replay, CLI, and property-based tests with a 90% branch-coverage release gate; the current result is 94.18%.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Policy and product specification](docs/PRODUCT_SPEC.md)
- [Threat model](docs/THREAT_MODEL.md)
- [NeMo comparison](docs/COMPETITIVE_ANALYSIS.md)
- [Benchmark](docs/BENCHMARK.md)
- [Project plan](PROJECT_PLAN.md)
- [Roadmap](ROADMAP.md)

Apache-2.0 licensed.
