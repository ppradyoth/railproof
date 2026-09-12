# Railguard project plan

## 1. Product definition

Railguard is a policy-as-code enforcement layer for LLM applications and agents. Developers configure security rails in YAML, call Railguard from an SDK or middleware, and receive an allow, deny, redact, retry, approval, or escalation decision.

The first release should be small enough to test with real applications but deep enough to demonstrate a clear security thesis: agent actions need explicit authorization and inspectable evidence.

## 2. Problem

Most guardrail implementations are scattered across prompts, callbacks, ad hoc regular expressions, and provider-specific code. That makes it hard to answer basic operational questions:

- Which policy blocked this request?
- Did the control inspect the user input, retrieved content, tool arguments, or output?
- Was the action blocked before or after execution?
- Is the control effective against realistic attacks?
- Can the same policy run against another model or agent framework?

Railguard makes those decisions explicit and testable.

## 3. Product boundary

### In scope

- Input, retrieval, output, and tool-call enforcement
- Tool allowlists and argument-level constraints
- Secret detection and redaction
- Prompt-injection and instruction-like-content detection
- Human approval gates for high-impact tools
- Structured audit events
- Offline policy testing against attack cases and benign cases
- Framework-neutral Python API

### Out of scope for v0.1

- Training or fine-tuning models
- A hosted dashboard
- A universal classifier for every harmful category
- Claims of complete prompt-injection prevention
- Replacing identity, authorization, DLP, or network controls
- Automatic execution of untrusted tools

## 4. Users

### Primary user

An engineer responsible for an LLM feature or agent who needs enforceable controls without rewriting the application around one model vendor.

### Secondary users

- Security engineers writing policies and attack tests
- Platform teams standardizing controls across applications
- Researchers measuring guardrail efficacy

## 5. Security thesis

The most valuable initial control point is the tool boundary. A model can produce an unsafe answer, but an agent can also take an unsafe action. Railguard therefore treats tool calls as authorization decisions, not merely text to moderate.

The system must distinguish:

- detection from enforcement
- a blocked attempt from a successful bypass
- a model judgment from a deterministic rule
- an observation from a confirmed security impact

## 6. Proposed architecture

```text
Application
    |
    v
Railguard SDK / middleware
    |
    +--> Policy loader and validator
    +--> Event normalizer
    +--> Deterministic checks
    +--> Model-backed detectors
    +--> Decision engine
    +--> Approval provider
    +--> Audit sink
    |
    +--> Model, retriever, or tool executor
```

### Core modules

#### Policy layer

Loads versioned YAML, validates schemas, resolves named detectors and actions, and rejects ambiguous policy definitions at startup.

#### Event layer

Normalizes user messages, retrieved chunks, model responses, tool calls, tool results, and approval outcomes into a common event format.

#### Detector layer

Supports deterministic detectors first, then model-backed detectors behind an explicit interface. Each detector returns a result, confidence, evidence spans, and detector metadata.

#### Decision engine

Combines matched policies into a deterministic decision. Policy precedence must be visible. A detector recommendation must never silently override an explicit deny or approval requirement.

#### Enforcement layer

Implements allow, deny, redact, retry, approval, and escalate. Tool checks must run before execution. Post-execution checks are for inspection and response handling, not pretending an action was prevented.

#### Audit layer

Emits structured events with policy version, event type, detector results, decision, latency, and redacted evidence. Raw secrets must never enter default logs.

## 7. Configuration design

The first configuration format should remain readable without learning a new language.

```yaml
version: "0.1"

defaults:
  on_detector_error: deny

rails:
  input:
    - id: prompt-injection
      detector: instruction_conflict
      action: deny

  tools:
    - id: restricted-tools
      match:
        names: [send_email, delete_file]
      action: approval
      approval_timeout: 300

    - id: outbound-data
      match:
        names: [http_request]
      detector: sensitive_data_in_arguments
      action: deny

  output:
    - id: secrets
      detector: secret_pattern
      action: redact
```

Configuration requirements:

- stable schema version
- unique policy IDs
- explicit stage and action
- deterministic precedence
- startup validation
- policy hash in every audit event
- safe defaults for detector or approval failures

## 8. MVP release

### MVP capabilities

1. Python package with synchronous and asynchronous APIs.
2. YAML policy loader with schema validation.
3. Input, output, and pre-tool-call interception.
4. Deterministic secret-pattern detector.
5. Tool allowlist and argument constraints.
6. Approval callback interface.
7. Structured decision and audit event models.
8. Offline test runner with benign and adversarial fixtures.
9. FastAPI integration example.
10. Documentation showing one model call, one RAG flow, and one tool-calling agent.

### MVP success criteria

- A developer can add Railguard to a small Python agent in under 30 minutes.
- A policy error fails at startup with a useful location and message.
- A dangerous tool call is blocked before the executor receives it.
- A secret is redacted from output and absent from the default audit record.
- Every decision is reproducible from the recorded policy version and event fixture.
- The test runner reports true positives, false positives, false negatives, and unresolved cases.

## 9. Delivery roadmap

### Phase 0: repository and contract

Deliver the policy schema, event model, decision vocabulary, threat model, and test fixture format.

Exit criteria: two example policies can be validated, rendered, and reviewed without implementation-specific assumptions.

### Phase 1: deterministic core

Implement policy loading, event normalization, rule evaluation, tool authorization, redaction, and audit events.

Exit criteria: unit tests cover precedence, fail-closed behavior, pre-execution blocking, redaction, and async execution.

### Phase 2: integration surface

Add framework-neutral wrappers, OpenAI-compatible examples, FastAPI middleware, and a tool executor interface.

Exit criteria: examples run locally with a fake model and fake tools, with no provider credential required.

### Phase 3: security detectors

Add instruction-conflict detection, sensitive-data-in-arguments detection, retrieval-content inspection, and detector evidence spans.

Exit criteria: each detector has benign controls, attack fixtures, known limitations, and measured results.

### Phase 4: evaluation and hardening

Add replay tests, latency measurements, policy mutation tests, fuzzing for configuration inputs, and concurrency tests.

Exit criteria: release report includes coverage, performance, failure modes, and cases where the control does not protect the application.

### Phase 5: public alpha

Publish examples, API documentation, threat model, benchmark fixtures, contribution rules, and a versioned release.

Exit criteria: an external developer can install, configure, run, and understand the limits of the project without private context.

## 10. Initial backlog

### P0

- Define `RailEvent`, `DetectorResult`, `PolicyMatch`, and `Decision` contracts.
- Define YAML schema and validation errors.
- Implement deterministic policy precedence.
- Implement tool name and argument matching.
- Implement allow, deny, redact, and approval actions.
- Implement secret-pattern detection with redaction spans.
- Implement JSON audit events with secret-safe defaults.
- Add fixture runner and initial attack/benign cases.

### P1

- Add retrieval-stage interception.
- Add detector plugin interface.
- Add model-backed detector adapter.
- Add OpenTelemetry-compatible trace correlation.
- Add policy dry-run mode.
- Add policy explain output for local debugging.
- Add latency and decision metrics.

### P2

- Add policy bundles and signed policy distribution.
- Add approval providers for common ticket or chat systems.
- Add a local replay UI only after the SDK contract is stable.
- Add language bindings only after Python usage is validated.

## 11. Threat model

### Assets

- secrets in prompts, context, tool arguments, and outputs
- external systems reachable through tools
- user and tenant data
- policy integrity
- audit records
- approval decisions

### Threats

- prompt injection in user input or retrieved content
- tool argument manipulation
- unauthorized high-impact tool execution
- secret exfiltration through tool calls or responses
- detector evasion and encoding tricks
- policy misconfiguration
- fail-open behavior after detector or approval errors
- audit log leakage
- replay or tampering with policy versions

### Trust boundaries

- user input to application
- retriever to agent context
- model to application
- model to tool executor
- Railguard to external detector
- application to audit sink

Railguard does not make the model trusted. Model output, retrieved content, and tool results remain untrusted at every boundary.

## 12. Evaluation strategy

Every security claim must include:

- exact fixture input
- expected policy behavior
- actual decision
- positive control
- benign control
- detector and policy versions
- whether the action was prevented before execution
- known limitations

Metrics:

- true-positive rate
- false-positive rate
- false-negative rate
- pre-execution prevention rate
- approval completion rate
- p50 and p95 added latency
- policy validation failure rate
- audit completeness

The benchmark must never present a blocked test case as proof of a production vulnerability. It measures the control under a defined fixture and configuration.

## 13. API shape

```python
decision = await guardrail.inspect_tool_call(
    name="send_email",
    arguments={"to": "user@example.com", "body": body},
    context=context,
)

if decision.requires_approval:
    await approval_provider.request(decision)

decision.enforce()
result = await executor.call(name, arguments)
```

The API should make the unsafe path difficult to write. The executor should not run until the decision has been enforced.

## 14. Repository structure

```text
railguard/
├── README.md
├── PROJECT_PLAN.md
├── pyproject.toml
├── src/railguard/
│   ├── policy/
│   ├── events/
│   ├── detectors/
│   ├── decisions/
│   ├── integrations/
│   └── audit/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── examples/
│   ├── basic_chat/
│   ├── rag/
│   └── tool_agent/
└── docs/
    ├── threat-model.md
    ├── policy-reference.md
    └── evaluation-methodology.md
```

## 15. Quality and release gates

- Formatting, linting, typing, and tests pass in CI.
- No default logs contain raw secrets.
- No tool executes before its pre-execution decision.
- Policy changes are covered by fixture tests.
- Detector failures follow the configured fail-safe behavior.
- Documentation states what each detector cannot establish.
- Security findings are reproducible from committed fixtures.
- Public examples use fake credentials and fake external systems.

## 16. Risks and decisions

### Risk: becoming a NeMo clone

Decision: focus the first release on security policy enforcement at the tool and data boundaries, with evidence and evaluation as first-class features.

### Risk: model-backed detectors create false confidence

Decision: expose detector uncertainty, retain deterministic controls, and publish false-positive and false-negative measurements.

### Risk: policy language becomes too complex

Decision: start with YAML and composable named detectors. Add a flow language only when real policies cannot be expressed cleanly.

### Risk: integrations dominate the project

Decision: keep a stable core event and decision API, then treat integrations as adapters.

### Risk: hosted control plane expands the scope

Decision: keep v0.1 self-hosted and local. Revisit hosted management only after SDK adoption and policy workflows are validated.

## 17. Public positioning

Railguard is an open-source policy-as-code layer for inspectable LLM and agent security decisions.

The strongest public proof will be:

- a working tool-call block before execution
- a policy explaining the decision
- an audit event without secret leakage
- a replayable evaluation showing both protection and failure cases

Do not market it as a complete solution to prompt injection. Market it as a practical enforcement and evaluation layer that makes security controls explicit.

## 18. First build session

1. Confirm the name and license.
2. Create the Python package and test runner.
3. Implement the event, decision, and policy contracts.
4. Add one end-to-end fake-agent example.
5. Write the first ten fixtures: five attack cases and five benign cases.
6. Verify that a blocked tool call never reaches the executor.
