# Railguard

Configurable security guardrails for LLM applications and agents.

Railguard sits between an application and its model, retrieval system, or tools. Teams define policies once, then enforce them across input, retrieved content, model output, and tool execution.

Railguard is built to beat NeMo Guardrails on the security-engineering workflow. Its focus is explainable control over agent behavior: prompt-injection resistance, sensitive-data handling, tool authorization, approval gates, and audit-ready decisions.

## Status

Pre-development. The product and implementation plan are in [PROJECT_PLAN.md](PROJECT_PLAN.md).

## Design target

```yaml
rails:
  input:
    - detect_prompt_injection
  tools:
    - require_approval_for: [send_email, delete_file]
    - deny_if: data_exfiltration
  output:
    - redact_secrets
```

Every decision should answer four questions:

1. What was inspected?
2. Which policy matched?
3. What action was taken?
4. What evidence supports the decision?

## Principles

- Policy before prompts. Security decisions must not depend only on a system prompt.
- Fail closed for explicitly dangerous actions.
- Preserve the original request and decision context for investigation.
- Make enforcement portable across model providers.
- Treat retrieved text and tool results as untrusted input.
- Measure false positives and false negatives instead of claiming perfect protection.

## Intended first integrations

- Python applications
- FastAPI middleware
- OpenAI-compatible chat and tool-calling clients
- LangChain and framework-neutral adapters

## License

License will be selected before the first public release.
