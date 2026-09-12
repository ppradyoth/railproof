# Product specification

## Contract

Railproof receives a normalized event and policy context, evaluates a compiled policy, enforces obligations, and returns a structured result. For tool calls, Railproof owns the path to the executor.

## Decision outcomes

| Outcome | Runtime behavior |
|---|---|
| `allow` | Execute after required non-blocking obligations finish |
| `deny` | Record the verdict and do not call the executor |
| `rewrite` | Produce new arguments, rerun policy, then require an allow decision |
| `require_approval` | Pause and bind approval to the exact action hash |
| `error` | Follow the policy's explicit failure mode, with deny as the default for tool execution |

No implicit allow outcome exists.

## Functional requirements

### Policy loading

- RP-POL-001: Validate schema version, stages, effects, predicates, references, and unique IDs at startup.
- RP-POL-002: Reject unsupported predicates and unknown enforcement stages.
- RP-POL-003: Detect rules shadowed by unconditional earlier rules.
- RP-POL-004: Produce an immutable policy hash.
- RP-POL-005: Explain the compiled rule order without running an agent.

### Tool enforcement

- RP-TOOL-001: Register tools with JSON Schema, risk, side effects, source/sink metadata, and an executor.
- RP-TOOL-002: Reject unknown tools before execution.
- RP-TOOL-003: Validate arguments before policy evaluation.
- RP-TOOL-004: Enforce exact values, sets, ranges, hostnames, path roots, recipients, and tenant boundaries.
- RP-TOOL-005: Support session counters and budgets.
- RP-TOOL-006: Prevent direct access to an executor through the documented integration path.

### Provenance and labels

- RP-DATA-001: Attach labels to user input, retrieved chunks, model output, tool arguments, and tool results.
- RP-DATA-002: Track declared derivation between source fields and destination fields.
- RP-DATA-003: Prevent untrusted content from adding authority labels.
- RP-DATA-004: Prevent sensitivity labels from disappearing without an explicit declassification rule.
- RP-DATA-005: Preserve tenant labels across transformations.

### Approval

- RP-APR-001: Bind approval to principal, tool, canonical arguments, policy hash, and expiry.
- RP-APR-002: Make approvals single use by default.
- RP-APR-003: Reject modified, expired, replayed, or cross-tenant approvals.
- RP-APR-004: Record the approver identity without placing approval secrets in logs.

### Evidence and replay

- RP-EVD-001: Emit event ID, decision ID, policy hash, matched rule IDs, outcome, obligations, and timing.
- RP-EVD-002: Hash or redact sensitive values by default.
- RP-EVD-003: Separate detector output from the final policy verdict.
- RP-EVD-004: Record whether the executor started and completed.
- RP-EVD-005: Reproduce deterministic decisions from a fixture and compiled policy.

### Testing

- RP-TST-001: Run adversarial and benign fixtures from the CLI.
- RP-TST-002: Report false positives, false negatives, unresolved cases, and pre-execution prevention.
- RP-TST-003: Mutate supported policy constructs and report whether tests detect the weakening.
- RP-TST-004: Verify that test fixtures do not call real external systems.

## Non-functional requirements

- RP-NFR-001: Deterministic checks add less than 5 ms p95 on the reference benchmark.
- RP-NFR-002: Core runtime works without a model or network call.
- RP-NFR-003: Sync and async applications receive equivalent decisions.
- RP-NFR-004: Concurrent sessions do not share principal, tenant, label, budget, or approval state.
- RP-NFR-005: Policy and evidence formats are versioned.
- RP-NFR-006: Default logging contains no raw prompt, tool argument, result, secret, or approval token.

## Policy semantics

The first policy format uses a closed set of typed predicates. It does not execute arbitrary Python, templates, or shell expressions.

Precedence:

1. invalid event or policy error
2. deterministic deny
3. required approval
4. rewrite
5. allow

A later allow cannot override a deny. A rewrite must pass through policy again. Approval satisfies one obligation but cannot erase an unrelated deny.

## Definition of alpha

Alpha means all P0 requirements have tests, the benchmark harness runs locally, and the same action policy works through one OpenAI-style adapter and one MCP adapter.

Alpha does not mean production ready.
