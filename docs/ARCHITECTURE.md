# Architecture

## Design rule

Separate policy compilation from runtime enforcement.

The compiler answers whether a policy is valid and enforceable. The runtime answers whether one exact event is authorized. Neither delegates authority to an LLM.

## Runtime flow

```text
Agent or application
        |
        v
Protocol adapter
        |
        v
Event normalizer -----> Label and provenance resolver
        |                         |
        +------------+------------+
                     v
              Compiled policy
                     |
                     v
              Decision engine
                     |
          +----------+----------+
          |          |          |
         deny     approval     allow
          |          |          |
          +----------+----------+
                     v
                Evidence sink
                     |
                     v
              Wrapped executor
```

The evidence sink records the decision before execution. It records executor start and completion as separate events. A missing completion event is observable. It is not rewritten as a successful block.

## Components

### Policy compiler

Parses versioned YAML into typed policy objects, resolves references, checks rule reachability, validates stages, and produces an immutable decision graph plus policy hash.

It rejects:

- unknown fields that affect security behavior
- unsupported enforcement points
- missing referenced labels or tools
- duplicate rule IDs
- allow rules shadowed by unconditional deny rules
- approval rules without a binding contract
- source-to-sink rules for sources or sinks the adapter cannot observe

### Protocol adapters

Adapters translate provider or framework events into the canonical model. They do not implement policy.

The first two adapters are:

- OpenAI-style function calls
- MCP tool calls and results

An adapter declares which enforcement stages and provenance fields it can guarantee. The compiler refuses a policy that depends on a guarantee the active adapter cannot provide.

### Event normalizer

Produces a canonical envelope:

```json
{
  "event_id": "evt_01...",
  "stage": "before_tool",
  "session_id": "ses_01...",
  "principal": {"id": "user_123", "tenant": "tenant_a"},
  "action": {
    "tool": "send_email",
    "arguments": {"to": "review@example.com", "body": "..."}
  },
  "labels": {},
  "parents": ["evt_00..."]
}
```

Canonical serialization is required for policy hashing, action hashing, approvals, and replay.

### Label and provenance resolver

Labels describe data, not authority. Initial alpha labels:

- `untrusted`
- `user_controlled`
- `retrieved`
- `model_generated`
- `sensitive`
- `secret`
- `tenant:<id>`

Provenance links fields across events. The alpha can require explicit derivation from adapters or application hooks. It must not pretend to infer perfect data lineage from arbitrary model output.

### Decision engine

Evaluates deterministic predicates over canonical events, labels, provenance, principal context, and session state.

Model-backed detectors return evidence records. Policy decides how to use that evidence. A detector cannot directly execute, approve, or declassify an action.

### Approval broker

Creates a canonical action hash over principal, tenant, tool, arguments, policy hash, and expiry. The approval provider signs or attests that exact hash.

Any argument change creates a new action and requires a new decision.

### Wrapped executor

The main API combines authorization and execution:

```python
result = await guarded_tools.call(
    "send_email",
    arguments,
    principal=principal,
    context=context,
)
```

This avoids the unsafe pattern where application code asks for a decision and then independently calls the tool.

### Evidence sink

Writes append-only JSONL in alpha. Values marked sensitive are redacted or hashed before serialization. Full-content capture requires an explicit sink and policy.

## State model

Alpha state is scoped to one session and one process. It supports:

- action count by tool
- cumulative numeric budget
- prior decision lookup
- approval nonce use
- event parent links

Distributed and cross-session state are later work.

## Failure behavior

| Failure | Before tool execution |
|---|---|
| Invalid policy | Application startup fails |
| Unsupported adapter guarantee | Application startup fails |
| Malformed action | Deny |
| Detector unavailable | Use the rule's declared failure behavior, default deny |
| Approval unavailable | Do not execute |
| Evidence sink unavailable | Do not execute for high-risk tools, configurable for low-risk tools |
| Executor failure | Record failure, never report a policy block |

## Security boundary

Railproof only controls tools called through its wrapped registry or a verified adapter interception point. Direct calls to the underlying tool bypass it.

Every integration document must state that boundary and include a bypass test.
