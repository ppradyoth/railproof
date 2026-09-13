# Product specification

## v0.1.0 contract

Railproof receives a normalized pre-tool event, evaluates a compiled policy, enforces any approval requirement, atomically reserves session limits, records evidence, and invokes a registered executor only after authorization.

| Outcome | Runtime behavior |
|---|---|
| `allow` | Reserve applicable limits and execute |
| `deny` | Record the verdict and do not execute |
| `require_approval` | Return an exact-action challenge; execute only after token verification |

No implicit allow exists. Deny takes precedence over approval, which takes precedence over allow. An unmatched action is denied.

## Implemented requirements

### Policy

- versioned `railproof.dev/v1alpha1` YAML
- safe loading, duplicate-key rejection, 1 MiB size limit, and closed fields
- declared tools with JSON Schema Draft 2020-12, risk, and sink metadata
- typed predicates: `eq`, `neq`, `in`, `not_in`, `lte`, `gte`, `has_label`, `derived_from`
- deterministic ordering and policy hash
- startup rejection for unsupported stages, operators, effects, fields, and schema references

### Enforcement

- framework-neutral registry for sync and async executors
- unknown-tool and argument-schema rejection before execution
- rules over action arguments, principal fields, roles, tool metadata, labels, provenance, call counts, and sums
- atomic process-local count and numeric-sum budgets by session
- bounded in-memory session tables with a secure default capacity of 10,000
- decision evidence before execution and separate executor started/completed/failed evidence

### Approval

- HMAC-SHA-256 token with a minimum 32-byte signing key
- binding to action hash, policy hash, principal, approver, expiry, and nonce
- rejection of modified, forged, malformed, expired, reused, and cross-principal tokens

### Adapters and replay

- OpenAI Chat Completions function-call normalization
- MCP JSON-RPC 2.0 `tools/call` normalization
- CLI commands: `validate`, `check`, and `replay`
- JSONL fixtures with expected versus actual outcomes

### Evidence

- built-in in-memory and append-only JSONL sinks
- bounded in-memory retention with a 10,000-record default
- event/session/tool identifiers, principal hash, policy/action/decision hashes, rules, reasons, and outcome
- no raw action arguments, approval token, prompt, or tool result in built-in evidence

## Non-functional gates

- Python 3.11, 3.12, and 3.13 CI matrix
- no model or network call in the core decision path
- Ruff and formatter clean
- `ty` type check clean
- at least 90% branch coverage; current measured coverage is 94.18%
- deterministic p95 below 5 ms; current local benchmark is 48 µs
- dependency audit and locked build in CI
- GitHub Actions pinned to commit SHAs with read-only repository permissions

## Security boundaries

- Only calls through `GuardedTools` are controlled.
- The host application attests labels and provenance; v0.1.0 does not infer them.
- State and nonce replay protection are process-local and reset on restart.
- The built-in approval broker is not a remote human-approval service.
- Rules compare fields to policy constants; field-to-field comparison is not implemented.
- Evidence files are append-only by behavior, not tamper-evident or remotely attested.
- Tool results and model text are outside the v0.1.0 enforcement stage.

## Deferred requirements

- automatic taint/label propagation and declassification
- adapter capability declarations and compile-time observability checks
- shadowed/unreachable rule analysis
- policy mutation testing
- tool-result schema, safety, and provenance checks
- persistent/distributed limits and approval nonces
- signed policy bundles and remote policy distribution
- hosted decision service, dashboard, TypeScript SDK, and additional provider adapters

Alpha means the implemented contract is runnable, tested, benchmarked, and explicit about its boundary. It does not mean production ready.
