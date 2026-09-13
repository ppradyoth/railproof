# Decision log

## Confirmed

### D001: Tool execution is the first enforcement boundary

Status: accepted.

The first release protects actions before execution. Input and output moderation can integrate later.

### D002: Authority is deterministic

Status: accepted.

Models and classifiers can provide evidence. They cannot grant authority, override a deny, or declassify data.

### D003: Railproof owns the wrapped execution path

Status: accepted.

Returning a boolean leaves enforcement to application code. The primary API authorizes and executes through one controlled path.

### D004: Evidence is part of the runtime contract

Status: accepted.

Every decision records policy identity, matched rules, timing, and executor state with secret-safe defaults.

### D005: Comparisons require matched scenarios

Status: accepted.

No general superiority claim is allowed without a versioned public benchmark.

## Accepted implementation decisions

### D006: Use `Railproof` as the project name

Status: accepted.

Reason: `Railguard` conflicts with an existing PyPI SDK. `Railproof` reflects the evidence and verification wedge. The repository is `ppradyoth/railproof`.

### D007: Use Apache-2.0

Status: accepted.

Reason: permissive commercial use plus an explicit patent grant.

### D008: Use YAML with typed predicates

Status: accepted.

Reason: easy review and strict validation. No arbitrary code or general expression language in alpha.

### D009: Support Python 3.11+

Status: accepted.

Reason: modern typing and async support without carrying older-runtime compatibility work into alpha.

### D010: Pin the comparison to NeMo 0.24.0

Status: accepted.

Reason: comparative claims must name the exact implementation and tested scope. The benchmark calls NeMo's real deterministic tool-call validator and does not model unsupported outcomes.

## Open

- public release timing; the repository remains private during hardening
- durable signing-key and nonce-store interfaces
- policy bundle signature and evidence-chain formats
- automatic provenance/label propagation design
- package publication name verification on PyPI
