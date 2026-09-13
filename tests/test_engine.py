import copy

import pytest

from railproof.engine import DecisionEngine
from railproof.models import Action, Event, Outcome, Principal, SessionSnapshot
from railproof.policy import CompiledPolicy, compile_policy


def make_event(
    tool: str,
    arguments: dict,
    *,
    labels: dict[str, frozenset[str]] | None = None,
    provenance: dict[str, tuple[str, ...]] | None = None,
) -> Event:
    return Event(
        event_id="evt_test",
        session_id="session_test",
        stage="before_tool",
        principal=Principal(id="user_1", tenant="tenant_a"),
        action=Action(tool=tool, arguments=arguments),
        labels=labels or {},
        provenance=provenance or {},
    )


def test_allows_explicitly_allowed_tool(policy: CompiledPolicy) -> None:
    decision = DecisionEngine(policy).decide(
        make_event("get_weather", {"city": "Bengaluru"}), SessionSnapshot()
    )

    assert decision.outcome is Outcome.ALLOW
    assert decision.matched_rules == ("allow-weather",)


def test_unknown_tool_is_denied(policy: CompiledPolicy) -> None:
    decision = DecisionEngine(policy).decide(make_event("delete_database", {}), SessionSnapshot())

    assert decision.outcome is Outcome.DENY
    assert decision.reason_codes == ("unknown_tool",)


def test_schema_valid_but_sensitive_action_is_denied(policy: CompiledPolicy) -> None:
    event = make_event(
        "send_email",
        {"to": "review@example.com", "body": "token-value"},
        labels={"action.arguments.body": frozenset({"sensitive"})},
    )

    decision = DecisionEngine(policy).decide(event, SessionSnapshot())

    assert decision.outcome is Outcome.DENY
    assert "block-sensitive-external" in decision.matched_rules
    assert "approve-email" in decision.matched_rules
    assert decision.reason_codes[0] == "sensitive_data_to_external_sink"


def test_untrusted_data_cannot_select_recipient(policy: CompiledPolicy) -> None:
    event = make_event(
        "send_email",
        {"to": "attacker@example.com", "body": "hello"},
        provenance={"action.arguments.to": ("retrieved.email",)},
    )

    decision = DecisionEngine(policy).decide(event, SessionSnapshot())

    assert decision.outcome is Outcome.DENY
    assert decision.reason_codes[0] == "untrusted_data_selected_recipient"


def test_email_without_deny_condition_requires_approval(policy: CompiledPolicy) -> None:
    decision = DecisionEngine(policy).decide(
        make_event("send_email", {"to": "review@example.com", "body": "hello"}),
        SessionSnapshot(),
    )

    assert decision.outcome is Outcome.REQUIRE_APPROVAL
    assert decision.reason_codes == ("external_side_effect",)


def test_invalid_arguments_are_denied_before_rules(policy: CompiledPolicy) -> None:
    decision = DecisionEngine(policy).decide(
        make_event("get_weather", {"city": 7}), SessionSnapshot()
    )

    assert decision.outcome is Outcome.DENY
    assert decision.reason_codes == ("invalid_arguments",)


def test_limit_is_enforced_before_allow_rule(policy: CompiledPolicy) -> None:
    decision = DecisionEngine(policy).decide(
        make_event("get_weather", {"city": "Bengaluru"}),
        SessionSnapshot(call_counts={"get_weather": 2}),
    )

    assert decision.outcome is Outcome.DENY
    assert decision.reason_codes == ("limit:weather-calls",)


def test_unsupported_stage_is_denied(policy: CompiledPolicy) -> None:
    event = make_event("get_weather", {"city": "Bengaluru"})
    event = Event(
        event_id=event.event_id,
        session_id=event.session_id,
        stage="after_tool",
        principal=event.principal,
        action=event.action,
    )
    decision = DecisionEngine(policy).decide(event, SessionSnapshot())
    assert decision.reason_codes == ("unsupported_stage",)


def test_noncanonical_action_is_denied(policy: CompiledPolicy) -> None:
    decision = DecisionEngine(policy).decide(
        make_event("get_weather", {"city": {"not", "json"}}), SessionSnapshot()
    )
    assert decision.outcome is Outcome.DENY
    assert decision.reason_codes == ("non_canonical_action",)


def _condition_policy(policy: CompiledPolicy, condition: dict) -> CompiledPolicy:
    raw = copy.deepcopy(policy.source)
    raw["rules"] = [
        {
            "id": "conditional-allow",
            "stage": "before_tool",
            "when": {"all": [condition]},
            "effect": "allow",
            "reason": "condition_matched",
        }
    ]
    raw["limits"] = []
    return compile_policy(raw)


def test_unmatched_known_tool_is_denied(policy: CompiledPolicy) -> None:
    conditional = _condition_policy(
        policy, {"field": "action.arguments.city", "op": "eq", "value": "Delhi"}
    )
    decision = DecisionEngine(conditional).decide(
        make_event("get_weather", {"city": "Bengaluru"}), SessionSnapshot()
    )
    assert decision.reason_codes == ("unmatched",)


def test_condition_operators_and_context_fields(policy: CompiledPolicy) -> None:
    cases = [
        ({"field": "action.arguments.city", "op": "neq", "value": "Delhi"}, SessionSnapshot()),
        (
            {"field": "action.arguments.city", "op": "in", "values": ["Bengaluru"]},
            SessionSnapshot(),
        ),
        (
            {"field": "action.arguments.city", "op": "not_in", "values": ["Delhi"]},
            SessionSnapshot(),
        ),
        ({"field": "principal.id", "op": "in", "values": ["user_1"]}, SessionSnapshot()),
        (
            {"field": "session.call_count.get_weather", "op": "lte", "value": 2},
            SessionSnapshot(call_counts={"get_weather": 1}),
        ),
        ({"field": "session.sum.cost", "op": "gte", "value": 3}, SessionSnapshot(sums={"cost": 4})),
    ]
    for condition, session in cases:
        conditional = _condition_policy(policy, condition)
        event = make_event("get_weather", {"city": "Bengaluru"})
        assert DecisionEngine(conditional).decide(event, session).outcome is Outcome.ALLOW


def test_numeric_comparison_rejects_non_numeric_actual(policy: CompiledPolicy) -> None:
    conditional = _condition_policy(
        policy, {"field": "action.arguments.city", "op": "lte", "value": 2}
    )
    decision = DecisionEngine(conditional).decide(
        make_event("get_weather", {"city": "Bengaluru"}), SessionSnapshot()
    )
    assert decision.reason_codes == ("unmatched",)


def test_sum_limit_rejects_over_budget_and_invalid_amount(policy: CompiledPolicy) -> None:
    raw = copy.deepcopy(policy.source)
    raw["tools"]["charge"] = {
        "risk": "high",
        "sink": "external",
        "schema": {"type": "object", "properties": {}, "additionalProperties": True},
    }
    raw["rules"].append(
        {
            "id": "allow-charge",
            "stage": "before_tool",
            "when": {"all": [{"field": "action.tool", "op": "eq", "value": "charge"}]},
            "effect": "allow",
            "reason": "test",
        }
    )
    raw["limits"].append(
        {"id": "spend", "tool": "charge", "kind": "sum", "argument": "amount", "max": 10}
    )
    engine = DecisionEngine(compile_policy(raw))
    assert engine.decide(
        make_event("charge", {"amount": 6}), SessionSnapshot(sums={"spend": 5})
    ).reason_codes == ("limit:spend",)
    assert engine.decide(make_event("charge", {"amount": -1}), SessionSnapshot()).reason_codes == (
        "limit:spend",
    )


def test_invalid_event_context_is_denied(policy: CompiledPolicy) -> None:
    event = make_event("get_weather", {"city": "Bengaluru"})
    malformed = Event(
        event_id=event.event_id,
        session_id="",
        stage=event.stage,
        principal=event.principal,
        action=event.action,
    )
    decision = DecisionEngine(policy).decide(malformed, SessionSnapshot())
    assert decision.reason_codes == ("invalid_event_context",)


@pytest.mark.parametrize(
    "session",
    [
        SessionSnapshot(call_counts={"get_weather": -1}),
        SessionSnapshot(call_counts={"get_weather": True}),
        SessionSnapshot(sums={"budget": float("nan")}),
        SessionSnapshot(sums={"budget": -1}),
    ],
)
def test_invalid_session_state_is_denied(policy: CompiledPolicy, session: SessionSnapshot) -> None:
    decision = DecisionEngine(policy).decide(
        make_event("get_weather", {"city": "Bengaluru"}), session
    )
    assert decision.reason_codes == ("invalid_session_state",)
