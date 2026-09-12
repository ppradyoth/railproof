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

## Proposed

### D006: Use `Railproof` as the project name

Status: proposed.

Reason: `Railguard` conflicts with an existing PyPI SDK. `Railproof` reflects the evidence and verification wedge. GitHub and package availability still need final verification.

### D007: Use Apache-2.0

Status: proposed.

Reason: permissive commercial use plus an explicit patent grant. Confirm before public release.

### D008: Use YAML with typed predicates

Status: proposed.

Reason: easy review and strict validation. No arbitrary code or general expression language in alpha.

### D009: Support Python 3.11+

Status: proposed.

Reason: modern typing and async support without carrying older-runtime compatibility work into alpha.

## Open

- final package and repository name
- exact policy schema library
- sync API support in alpha or async-only core
- evidence canonicalization format
- approval signature format
- reference machine for performance claims
- public versus private GitHub repository
