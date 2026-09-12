# Railproof project plan

Goal: build the strongest open-source security contract and enforcement layer for tool-using AI agents.

## Product thesis

Models can propose actions. They cannot grant themselves authority.

Railproof places a policy enforcement point immediately before every tool execution. It evaluates the requested action against the authenticated principal, exact arguments, data provenance, trust labels, prior actions, budgets, approvals, and policy version.

The output is a structured decision. The runtime either executes the approved action through a controlled wrapper or proves that it did not execute.

## What we got wrong in the first draft

The first plan treated tool validation, evaluation, tracing, provider portability, and explainability as open territory. NeMo Guardrails already covers substantial parts of that surface.

The first plan also used “beat NeMo” before defining:

- the category where Railproof intends to win
- the same scenarios for both products
- measurable acceptance criteria
- evidence required for a comparison
- the capabilities already offered by other agent policy engines

That is fixed. Railproof will compete on verifiable agent-action security, not broad conversational guardrails.

## Product wedge

Railproof combines four capabilities in one contract:

1. **Action authorization** checks the exact tool, target, arguments, principal, and session state before execution.
2. **Information-flow enforcement** tracks where data came from and where it is allowed to go.
3. **Policy verification** catches missing enforcement points, conflicting rules, unsupported predicates, and weakened controls before deployment.
4. **Decision proof** records enough normalized evidence to explain and replay every verdict without storing raw secrets by default.

The first release does not need to beat NeMo at dialog control, content moderation breadth, model integrations, or deployment scale. It needs to beat NeMo at these four jobs with public evidence.

## Users

### Application engineer

Needs to put a reliable checkpoint around an existing agent without replacing the framework or model provider.

### Security engineer

Needs policies that can be reviewed, tested, traced to exact events, and challenged with adversarial fixtures.

### Platform engineer

Needs one enforcement contract across multiple agent frameworks, model providers, and tool protocols.

## Product requirements

The full requirements and acceptance tests live in [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md).

The first alpha must:

- intercept every registered tool call before execution
- deny tools and argument values outside explicit policy
- attach trust and sensitivity labels to normalized data
- propagate labels through declared transformations
- block prohibited source-to-sink flows
- issue approvals bound to exact action hashes
- reject invalid or incomplete policy at startup
- emit secret-safe evidence for every decision
- replay a decision without contacting a model
- run adversarial, benign, and mutation tests from the CLI

## Security invariants

1. A denied action never reaches the wrapped executor.
2. An unregistered tool never executes through the wrapped executor.
3. Approval for one action cannot authorize another action.
4. Untrusted content cannot grant authority or remove a label.
5. A detector cannot silently override a deterministic deny.
6. An unsupported policy construct stops deployment.
7. Default evidence does not contain raw secrets.
8. The decision identifies the exact policy version used.

These are testable contracts, not marketing language.

## Core primitives

| Primitive | Purpose |
|---|---|
| Principal | Authenticated user, service, tenant, or agent identity |
| Event | Normalized input, retrieval, model, tool-call, tool-result, or approval record |
| Action | Tool name, target, arguments, and declared side effects |
| Label | Trust, sensitivity, tenant, provenance, or policy metadata attached to data |
| Policy | Versioned rules evaluated at named enforcement stages |
| Decision | Allow, deny, rewrite, require approval, or error |
| Obligation | Required work before execution, such as redact, log, or obtain approval |
| Evidence | Matched fields, rule IDs, hashes, detector results, and event links |

## Runtime boundary

Railproof owns the call to the registered executor. An API that only returns `allowed: true` is too easy to bypass accidentally.

```python
result = await guarded_tools.call(
    "send_email",
    {"to": recipient, "body": body},
    principal=principal,
    context=context,
)
```

The wrapper normalizes the action, evaluates policy, resolves required approval, records the decision, and calls the underlying tool only after all obligations pass.

## Scope

### Version 0.1

- Python 3.11+
- local library and CLI
- YAML policy
- framework-neutral tool registry
- OpenAI-style function-call adapter
- MCP adapter
- exact argument constraints
- principal and tenant context
- trust and sensitivity labels
- local provenance graph
- deny and approval enforcement
- JSONL evidence and deterministic replay
- benchmark harness

### Later

- Anthropic and framework-specific adapters
- distributed policy decision service
- signed policy bundles
- external identity and approval providers
- OPA and Cedar interoperability
- persistent cross-session budgets
- TypeScript SDK

### Not in scope

- training safety classifiers
- replacing model moderation
- controlling general conversation flow
- claiming complete prompt-injection prevention
- sandboxing arbitrary code
- replacing IAM, DLP, network controls, or transaction authorization
- hosted management before the local contract is proven

## Architecture

The design lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The critical split is compile time versus runtime.

Compile time validates policy and creates an immutable decision graph. Runtime evaluates normalized events against that graph. Model-backed detectors can add evidence, but they do not define authority.

## Evidence standard

Every security claim requires:

- exact fixture and policy version
- expected and actual decision
- benign control
- positive control where applicable
- proof of whether the executor was reached
- detector output separated from policy verdict
- latency and external calls
- known bypasses and unresolved cases

The benchmark specification is in [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Competitive objective

The target is not “more features than NeMo.” The target is a documented win for agent-action security.

| Dimension | Alpha gate |
|---|---|
| Enforcement | 100% of denied benchmark actions stopped before executor entry |
| Replay | 100% of deterministic decisions reproduced from evidence artifacts |
| Policy mutation | Test suite kills at least 90% of supported policy mutations |
| Safety | Zero raw seeded secrets in default logs |
| Portability | Same policy passes against OpenAI-style and MCP adapters |
| Usability | New user reaches first denied tool call in under 10 minutes |
| Performance | Deterministic p95 overhead below 5 ms on the reference machine |

Detector accuracy thresholds will be set per detector. A single aggregate accuracy number would hide the failure mode that matters.

## Delivery

[ROADMAP.md](ROADMAP.md) defines a 12-week, one-developer path to public alpha. Each milestone ends in running evidence, not document completion.

## Publication gate

Do not publish until all four conditions hold:

1. The final name and package availability are verified.
2. The license decision is confirmed.
3. One end-to-end action is blocked before execution and replayed from evidence.
4. The README contains measured results instead of superiority language.

## Current state

Confirmed:

- product category
- narrow competitive wedge
- Python-first local alpha
- tool boundary as the first enforcement point
- evidence-first evaluation standard

Proposed:

- `Railproof` as the name
- Apache-2.0 as the license
- YAML as the first policy format

Blocked:

- GitHub remote creation because the current `gh` authentication is invalid

No implementation or benchmark result exists yet.
