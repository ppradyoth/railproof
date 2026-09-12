# Competitive analysis

Research date: 2026-09-12.

## Correction to the original plan

NeMo Guardrails already provides broad input, retrieval, dialog, execution, and output rails. It also has policy evaluation, an Eval UI, OpenTelemetry tracing, tool-call support, and a server.

So Railproof cannot differentiate on “configurable rails,” “tool support,” “evaluation,” “tracing,” or “provider support” as generic claims.

## NeMo baseline

| Confirmed capability | Evidence |
|---|---|
| Input, retrieval, dialog, execution, and output rails | [Architecture overview](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/how-it-works) |
| YAML, Colang, custom actions, SDK, and server | [Configuration overview](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/overview) |
| Policy evaluation for compliance, resource use, and latency | [Evaluate configuration](https://docs.nvidia.com/nemo/guardrails/evaluation/evaluate-configuration) |
| OpenTelemetry tracing and optional content capture | [Tracing](https://docs.nvidia.com/nemo/guardrails/observability/tracing) |
| Local tool name and JSON Schema validation | [Tool calling](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/guardrail-catalog/tool-calling) |

## Documented tool-rail boundaries we can target

These are documented limits or behavior, not vulnerability claims.

- Tool-call rails are experimental and limited to the IORails engine.
- The documented IORails tool path supports the OpenAI Chat Completions wire format.
- Tool-call validation checks the declared tool name and JSON Schema arguments.
- Tool-result validation checks structural linkage and well-formed content. It does not enforce a response schema, content safety, or server-verified provenance.
- `check()` and `check_async()` do not run tool-call or tool-result rails.
- An incompatible IORails configuration can fall back to the older engine unless strict construction is requested.

Source: [NeMo tool-calling documentation](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/guardrail-catalog/tool-calling).

## Other products invalidate an easy wedge

Capability-based authorization alone is not new.

The `agent-policy-engine` project claims deterministic policy, action registries, authority tokens, provenance, runtime state, MCP scanning, approvals, and external policy adapters. Another TypeScript project with the same name claims spend limits, authority levels, path protection, and pre-tool-call decisions.

These are product claims from their public project pages. They have not been independently tested here.

- [Python Agent Policy Engine](https://pypi.org/project/agent-policy-engine/1.0.2/)
- [TypeScript agent-policy-engine](https://github.com/Princeu3/agent-policy-engine)

Railproof therefore needs the combined wedge of enforceable information flow, compile-time policy verification, action-bound approval, deterministic replay, and policy mutation testing.

## Category Railproof should own

**Verifiable security contracts for agent actions.**

Not a conversational flow language. Not a bag of safety classifiers. Not a proxy that returns a risk score.

The project wins when a security engineer can prove:

1. which data influenced an action
2. which authority allowed or denied it
3. whether the action reached the executor
4. whether policy tests detect a weakened control
5. whether the same contract holds across adapters

## Fair comparison matrix

| Scenario | NeMo baseline | Railproof target |
|---|---|---|
| Unknown tool | Name allowlist | Name allowlist |
| Invalid arguments | JSON Schema | JSON Schema |
| Disallowed recipient with valid schema | Custom implementation required | Built-in typed argument policy |
| Untrusted retrieved value becomes recipient | Custom implementation required | Built-in provenance and flow rule |
| Approval reused after argument change | Custom implementation required | Action-bound single-use approval |
| Cross-step spend limit | Custom implementation required | Built-in session state policy |
| Tool result provenance | Structural linkage | Adapter-attested source plus labels |
| Policy typo | Configuration-dependent behavior | Compile failure |
| Weakened policy | User-authored evaluation | Built-in mutation testing |
| Decision replay | Trace and evaluation tooling | Offline deterministic replay artifact |
| MCP tool path | Not the documented IORails wire format | First-release adapter target |

“Custom implementation required” does not mean NeMo cannot support the scenario. It means the documented built-in tool rail does not establish the target property by itself.

## Claim policy

Before public alpha, say:

> Railproof is designed to provide verifiable security contracts for agent actions.

After the benchmark, a comparative claim can name only the tested version, scenario, configuration, and result.

Never say “beats NeMo” without the benchmark artifact.
