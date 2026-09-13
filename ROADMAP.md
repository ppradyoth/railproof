# Roadmap

## v0.1.0 status

The initial 12-week outline below was compressed into the first implementation pass. The strict policy compiler, decision engine, wrapped executor, explicit labels/provenance, approval binding, session limits, adapters, evidence, replay CLI, packaging, CI, and NeMo comparison are implemented.

Still open from the original plan: rule reachability/shadow analysis, automatic label propagation, tool-result enforcement, policy mutation testing, adapter capability declarations, full clean-machine usability timing, and public alpha publication.

Original assumption: one primary developer, 12 weeks to public alpha.

## Week 1: contract

Deliver:

- canonical event, action, principal, label, decision, and evidence models
- first policy schema
- compiler error taxonomy
- ten executable fixtures

Exit gate: policies for unknown tool, disallowed recipient, and approval binding compile into a deterministic rule graph.

## Weeks 2-3: policy compiler

Deliver:

- YAML parser and strict schema validation
- typed predicate registry
- rule precedence
- unsupported-stage detection
- shadowed-rule detection
- policy hash and explain output

Exit gate: malformed and unenforceable policies fail before application startup. Unit tests cover every compiler error.

## Weeks 4-5: enforcement runtime

Deliver:

- tool registry
- canonical argument serialization
- wrapped sync and async executors
- allow, deny, and error outcomes
- executor spy test harness
- JSONL evidence sink

Exit gate: no denied fixture reaches executor entry under normal, concurrent, or exception paths.

## Week 6: labels and provenance

Deliver:

- trust and sensitivity labels
- parent event links
- explicit field derivation hooks
- source-to-sink predicates
- declassification contract

Exit gate: indirect-injection and secret-exfiltration fixtures pass with benign controls. Documentation states where provenance is application-declared rather than inferred.

## Week 7: approval and state

Deliver:

- action-bound approval artifact
- expiry and single-use nonce
- session counters and numeric budgets
- replay and substitution tests

Exit gate: changed, expired, reused, and cross-tenant approvals fail.

## Week 8: adapters

Deliver:

- OpenAI-style function-call adapter
- MCP tool-call and result adapter
- adapter capability declaration
- integration bypass tests

Exit gate: one policy produces equivalent decisions through both adapters.

## Week 9: evaluation tooling

Deliver:

- fixture CLI
- benign, adversarial, and unresolved outcomes
- executor evidence
- latency metrics
- deterministic replay
- policy mutation runner

Exit gate: benchmark artifact is produced from one command without external credentials.

## Week 10: NeMo comparison

Deliver:

- pinned NeMo environment
- matched scenario configurations
- built-in versus custom-code accounting
- raw benchmark artifacts
- limitations log

Exit gate: every comparative statement links to a fixture, configuration, and executor observation.

## Week 11: hardening

Deliver:

- concurrency tests
- fuzz tests for policy and canonical serialization
- secret-leak tests
- packaging and clean-environment install test
- dependency and license review

Exit gate: release checklist passes on Linux and macOS.

## Week 12: public alpha

Deliver:

- final name and package
- Apache-2.0 or confirmed replacement license
- quickstart
- three complete examples
- threat model
- benchmark report
- security policy and contribution guide
- `v0.1.0-alpha.1`

Exit gate: a new user reaches the first denied tool action in under 10 minutes from a clean environment.

## P0 backlog

| ID | Work item | Depends on |
|---|---|---|
| RP-001 | Canonical data models | None |
| RP-002 | Policy schema v1alpha1 | RP-001 |
| RP-003 | Compiler and error taxonomy | RP-002 |
| RP-004 | Rule precedence and conflict checks | RP-003 |
| RP-005 | Tool registry and wrapped executor | RP-001 |
| RP-006 | Argument constraints | RP-003, RP-005 |
| RP-007 | Label propagation | RP-001 |
| RP-008 | Source-to-sink enforcement | RP-006, RP-007 |
| RP-009 | Approval binding | RP-001, RP-005 |
| RP-010 | Session budgets | RP-001, RP-005 |
| RP-011 | Evidence sink | RP-001 |
| RP-012 | Deterministic replay | RP-003, RP-011 |
| RP-013 | Mutation testing | RP-003 |
| RP-014 | OpenAI-style adapter | RP-005 |
| RP-015 | MCP adapter | RP-005 |
| RP-016 | Benchmark CLI | RP-011, RP-012, RP-013 |

## Explicitly deferred

- web dashboard
- hosted policy service
- general conversational rails
- broad classifier catalog
- custom flow language
- JavaScript or TypeScript SDK
- Kubernetes deployment
- billing and commercial packaging
