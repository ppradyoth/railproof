# Threat model

## Objective

Prevent an AI agent from turning untrusted instructions, sensitive data, or excess authority into an unauthorized external action through a protected tool boundary.

## Protected assets

- user and tenant data
- secrets and credentials
- files, messages, transactions, and external systems reachable through tools
- approval authority
- policy integrity
- evidence integrity
- session budgets and counters

## Adversaries

- malicious user controlling direct input
- attacker controlling retrieved content, documents, websites, emails, or tool results
- compromised or misconfigured tool server
- curious or manipulated model
- application developer who accidentally bypasses the enforcement path
- tenant attempting cross-tenant access

The model is never a trusted authority.

## Trust boundaries

1. User input enters the application.
2. Retrieved or tool-provided content enters model context.
3. Model output becomes a proposed action.
4. Railproof decides whether the action can reach the executor.
5. Tool results return to the agent.
6. Evidence leaves Railproof for storage or telemetry.
7. Approval enters from a human or external system.

## Threats and controls

| Threat | Required control | Verification |
|---|---|---|
| Unknown tool call | Default-deny tool registry | Executor spy remains untouched |
| Schema-valid but unauthorized argument | Argument and context policy | Denied target never reaches executor |
| Indirect prompt injection | Trust labels plus source-to-sink rule | Retrieved instruction cannot trigger protected sink |
| Sensitive-data exfiltration | Sensitivity propagation and sink restriction | Seeded secret absent from external call |
| Confused deputy | Principal and tenant binding | Cross-principal fixture denied |
| Approval replay | Single-use nonce and action hash | Second execution denied |
| Approval substitution | Exact argument and policy binding | Modified action denied |
| Multi-step budget abuse | Session counters and budgets | Action crossing threshold denied |
| Policy typo or unsupported feature | Compile-time rejection | Application does not start |
| Rule shadowing | Compiler analysis and mutation tests | Weakening detected before release |
| Audit leakage | Redaction and hashing by default | Seeded secrets absent from JSONL |
| Direct executor bypass | Wrapped registry and integration test | Bypass path documented or blocked |

## Security invariants

- No deny decision reaches executor entry.
- No approval authorizes a different action hash.
- No lower-trust event grants higher authority.
- No sensitivity label disappears without a named declassification rule.
- No deterministic deny is overridden by detector output.
- No unsupported policy deploys silently.
- No default evidence contains raw seeded secrets.

## Known limits

Railproof cannot:

- control direct tool calls outside its integration boundary
- prove semantic equivalence between arbitrary natural-language strings
- establish perfect provenance through an unconstrained model transformation
- stop abuse performed with authority explicitly granted by policy
- replace tool-side authorization or transaction validation
- guarantee a model will produce safe text
- secure a compromised host process

## Test discipline

Each threat test includes the attack fixture, an expected deny or approval outcome, a benign control, the exact policy, the executor observation, and the evidence record.

A detector alert is not a prevented attack. Prevention is established only when the protected executor did not receive the action.
