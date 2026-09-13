from pathlib import Path

import pytest

from railproof.policy import CompiledPolicy, load_policy


@pytest.fixture
def policy_path(tmp_path: Path) -> Path:
    path = tmp_path / "policy.yaml"
    path.write_text(
        """
apiVersion: railproof.dev/v1alpha1
kind: AgentSecurityPolicy
defaults:
  unmatched: deny
tools:
  get_weather:
    risk: low
    sink: internal
    schema:
      type: object
      additionalProperties: false
      properties:
        city:
          type: string
      required: [city]
  send_email:
    risk: high
    sink: external
    schema:
      type: object
      additionalProperties: false
      properties:
        to:
          type: string
        body:
          type: string
      required: [to, body]
rules:
  - id: block-sensitive-external
    stage: before_tool
    priority: 10
    when:
      all:
        - field: tool.sink
          op: eq
          value: external
        - field: action.arguments.body
          op: has_label
          value: sensitive
    effect: deny
    reason: sensitive_data_to_external_sink
  - id: block-untrusted-recipient
    stage: before_tool
    priority: 20
    when:
      all:
        - field: action.tool
          op: eq
          value: send_email
        - field: action.arguments.to
          op: derived_from
          value: retrieved.email
    effect: deny
    reason: untrusted_data_selected_recipient
  - id: approve-email
    stage: before_tool
    priority: 30
    when:
      all:
        - field: action.tool
          op: eq
          value: send_email
    effect: require_approval
    reason: external_side_effect
  - id: allow-weather
    stage: before_tool
    priority: 40
    when:
      all:
        - field: action.tool
          op: eq
          value: get_weather
    effect: allow
    reason: read_only_tool
limits:
  - id: weather-calls
    tool: get_weather
    kind: count
    max: 2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def policy(policy_path: Path) -> CompiledPolicy:
    return load_policy(policy_path)
