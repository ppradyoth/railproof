# Railproof

Security contracts for AI agent actions.

Railproof compiles readable policy into a mandatory checkpoint between an agent and its tools. It decides whether an action is allowed, denied, rewritten, or held for approval. Every decision carries the rule, evidence, policy hash, and event chain needed to replay it.

This is the working project name. `Railguard` was dropped because an existing `railguard-sdk` package already uses it.

## The wedge

General guardrail frameworks already moderate model input and output, guide conversations, validate tool names and schemas, evaluate policies, and emit traces. Railproof starts where those controls stop:

- authorize the exact action, target, arguments, principal, and session state
- track untrusted and sensitive data across model, retrieval, and tool boundaries
- prevent prohibited information flows before a tool executes
- bind approvals to one exact action instead of trusting a generic yes/no response
- compile policy before runtime and reject gaps, conflicts, and unsupported enforcement points
- replay decisions deterministically and mutation-test the policy suite

## Target configuration

```yaml
apiVersion: railproof.dev/v1alpha1
kind: AgentSecurityPolicy

tools:
  send_email:
    risk: high
    sink: external

rules:
  - id: block-untrusted-recipient
    stage: before_tool
    match:
      tool: send_email
      arguments.to:
        derives_from: untrusted
    effect: deny

  - id: approve-sensitive-email
    stage: before_tool
    match:
      tool: send_email
      arguments.body:
        contains_label: sensitive
    effect: require_approval
    approval:
      bind: [tool, arguments, policy_hash]
      expires_in: 5m
```

## What counts as success

Railproof earns a comparison with NeMo only after the same public scenarios run against both systems. The benchmark must include attacks, benign controls, false positives, false negatives, latency, setup time, and proof that denied actions never reached the executor.

No benchmark result exists yet. No superiority claim has been earned yet.

## Project status

Planning complete. Implementation has not started.

- [Project plan](PROJECT_PLAN.md)
- [Product specification](docs/PRODUCT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Competitive analysis](docs/COMPETITIVE_ANALYSIS.md)
- [Benchmark specification](docs/BENCHMARK.md)
- [Roadmap](ROADMAP.md)
- [Decision log](docs/DECISIONS.md)

## Intended first release

The first alpha will be a Python library with a framework-neutral enforcement API, YAML policies, a wrapped tool executor, deterministic policy checks, trust labels, approval binding, JSONL evidence, and a local replay CLI.

No hosted service. No dashboard. No custom policy language until the core security contract works.
