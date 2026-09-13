# Benchmark

## Reproduce

```bash
uv sync --group benchmark
uv run python benchmarks/compare_nemo.py --iterations 10000
```

The dependency group pins `nemoguardrails==0.24.0`; `uv.lock` pins the complete environment. The runner defaults to [benchmarks/policy.yaml](../benchmarks/policy.yaml) and can write machine-readable JSON with `--output`.

## Method

The comparison isolates model-free tool-call authorization. It uses no model, API, network, or real side effect.

Railproof evaluates each canonical event through `DecisionEngine`. NeMo evaluates the equivalent function call through its real v0.24.0 `ToolCallRailAction._validate` implementation and `Toolset`. The internal action method is used deliberately to isolate NeMo's documented built-in allowlist and JSON Schema behavior from provider transport and model latency.

Each attack family includes a benign control. Expected outcomes are security requirements defined before the decision. An `allow` does not count as success when the requirement is `deny` or `require_approval`.

Latency is wall-clock `perf_counter_ns()` around one decision. The runner cycles across all cases and reports p50, p95, and p99. It does not claim production throughput.

## Scenario set

| ID | Security property | Control |
|---|---|---|
| unknown-tool | Unknown tools do not execute | Declared weather tool passes |
| missing-argument | Schema-invalid arguments do not execute | Schema-valid weather arguments pass |
| disallowed-host | Schema-valid target policy is enforced | Approved host passes |
| retrieved-recipient | Retrieved data cannot select an email recipient | Application-selected email requires approval |
| sensitive-body | Sensitive-labeled data cannot reach external email | Non-sensitive email requires approval |
| transfer-over-session-budget | Cumulative state blocks threshold crossing | Transfer at the threshold passes |

Railproof's separate test suite verifies properties that are not assigned synthetic NeMo outcomes here: denied executor non-entry, atomic concurrent limits, approval action binding, expiry, forgery rejection, single use, evidence redaction, OpenAI/MCP equivalence, deterministic hashing, malformed policy rejection, and replay.

## Result

The checked-in run on macOS arm64, Python 3.11.2, Railproof 0.1.0, and NeMo Guardrails 0.24.0 produced:

- Railproof: 10/10
- NeMo built-in tool-call rail: 5/10
- Railproof latency: 44 µs p50, 48 µs p95, 57 µs p99
- NeMo latency: 492 µs p50, 517 µs p95, 575 µs p99

See the [raw JSON result](benchmark-results/v0.1.0-nemo-0.24.0.json).

## Limitations

- This does not compare NeMo's input/output/retrieval/dialog rails, model-backed detectors, server, or telemetry.
- NeMo can add semantic authorization through custom actions; the benchmark measures its built-in tool-call validator.
- The runner imports one internal NeMo action method. The pinned version and lock protect reproducibility, but a future NeMo release may require harness changes.
- Labels and provenance are trusted benchmark inputs, matching Railproof v0.1.0's application-attested boundary.
- Local microbenchmarks are sensitive to machine load and Python/runtime versions.

## Future benchmark expansion

Planned additions include tool-result response schemas, server-attested provenance, persistent multi-process limits, mutation testing, memory at 1,000 sessions, and full IORails request-path measurements with a mocked model transport.
