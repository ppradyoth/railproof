# Architecture

## Security invariant

An application must not receive an executable tool result unless the exact action passed the compiled policy and any required approval. Decisions never delegate authority to an LLM.

```text
Provider event -> adapter -> canonical Event -> DecisionEngine
                                                | deny
                                                | require approval
                                                | allow
                                                v
                                         evidence record
                                                v
                                        wrapped executor
```

## Implemented components

### Policy compiler

`load_policy()` reads at most 1 MiB through a custom loader derived from PyYAML `SafeLoader`. It caps YAML aliases at 100 and rejects duplicate keys, unknown fields, non-string mapping keys, unsupported stages/operators, invalid JSON Schema, all schema references, duplicate rule/limit IDs, undeclared limit tools, and any unmatched default other than `deny`.

The compiler returns immutable policy objects and a SHA-256 hash over canonical JSON data. Rule order is stable by priority and ID.

### Canonical event and hashing

The event contains the principal, tenant, roles, session, tool, arguments, labels, and provenance. Canonicalization sorts object keys, rejects non-string keys, non-finite numbers, unsupported types, cycles, and nesting beyond 64 levels.

The action hash binds:

- policy hash
- session ID
- principal ID, tenant, and roles
- tool and complete arguments
- labels and provenance

### Decision engine

The engine evaluates locally with no model or network call. It validates arguments using JSON Schema Draft 2020-12, checks session limits, evaluates typed conditions, and applies fixed precedence:

```text
deny > require_approval > allow > unmatched deny
```

Conditions support equality, inequality, membership, numeric bounds, field labels, and explicit derivation sources. Labels and provenance are supplied by the application or adapter; Railproof does not infer them.

### Approval broker

The built-in broker uses HMAC-SHA-256 with a minimum 32-byte key. A token binds the action hash, policy hash, principal, approver, expiry, and random nonce. Verification rejects signature changes, action/policy/principal changes, naive or expired timestamps, malformed payloads, and nonce reuse.

The broker is process-local. A production distributed deployment needs an external atomic nonce store and managed signing key.

### Wrapped executor

`GuardedTools.call()` canonicalizes caller arguments once into isolated event and execution snapshots, constructs the event, locks state by session, records the decision, denies or verifies approval, atomically reserves limits, and only then invokes the registered sync or async executor with the authorized snapshot. Executor start, completion, and failure are distinct evidence records.

Holding the session lock through policy and reservation prevents concurrent calls from overspending a count or sum limit. The lock is released before the underlying tool runs while an in-flight lease prevents teardown. Session IDs must be non-empty, principal IDs must be non-empty, and the process rejects new sessions after a configurable capacity that defaults to 10,000. Applications release completed state with `close_session()`; teardown rejects sessions with active executions.

### Evidence

The in-memory and JSONL sinks record event/session IDs, a hashed principal, tool name, action/policy/decision hashes, outcome, matched rules, and reason codes. Raw arguments are not stored by the built-in sinks. The default in-memory sink retains the newest 10,000 records; JSONL is the durable append-only option.

### Adapters and replay

The OpenAI adapter accepts one Chat Completions function-call object. The MCP adapter accepts one JSON-RPC 2.0 `tools/call` request. Both normalize into the same `Event`; policy remains protocol-independent.

The replay CLI loads JSONL cases, reconstructs events and session snapshots, and compares actual outcomes with expected outcomes.

## Failure behavior

| Failure | Behavior before execution |
|---|---|
| Invalid or oversized policy | Startup/compile error |
| Unknown tool or malformed action | Deny |
| Invalid arguments | Deny |
| Session limit exceeded | Deny |
| Approval unavailable, forged, expired, changed, or reused | Do not execute |
| Decision evidence sink raises | Do not execute |
| Executor missing | Do not execute |
| Executor raises | Record failure and propagate |

## Explicit non-goals for v0.1.0

- no direct-call sandbox: code holding the raw executor can bypass Railproof
- no automatic taint tracking or provenance attestation
- no post-tool/tool-result rail
- no argument rewrite
- no persistent or distributed session state
- no hosted control plane, UI, or policy distribution
- no model-backed content safety detector

These constraints are security boundaries, not implied features.
