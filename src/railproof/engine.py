from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator, FormatChecker

from railproof.canonical import digest_json
from railproof.exceptions import CanonicalizationError
from railproof.models import Decision, Event, Outcome, SessionSnapshot

if TYPE_CHECKING:
    from railproof.policy import CompiledPolicy, Condition, Limit, Rule

_MISSING = object()


class DecisionEngine:
    def __init__(self, policy: CompiledPolicy) -> None:
        self.policy = policy
        self._validators = {
            name: Draft202012Validator(tool.schema, format_checker=FormatChecker())
            for name, tool in policy.tools.items()
        }

    def decide(self, event: Event, session: SessionSnapshot) -> Decision:
        invalid_reason = self._invalid_context(event, session)
        if invalid_reason is not None:
            action_hash = digest_json(
                {
                    "event_id": str(event.event_id),
                    "policy_hash": self.policy.policy_hash,
                    "invalid": True,
                }
            )
            return self._decision(Outcome.DENY, action_hash, (), (invalid_reason,))
        try:
            action_hash = self.action_hash(event)
        except CanonicalizationError:
            action_hash = digest_json(
                {
                    "event_id": event.event_id,
                    "policy_hash": self.policy.policy_hash,
                    "tool": event.action.tool,
                    "uncanonical": True,
                }
            )
            return self._decision(Outcome.DENY, action_hash, (), ("non_canonical_action",))
        if event.stage != "before_tool":
            return self._decision(Outcome.DENY, action_hash, (), ("unsupported_stage",))
        tool = self.policy.tools.get(event.action.tool)
        if tool is None:
            return self._decision(Outcome.DENY, action_hash, (), ("unknown_tool",))
        errors = tuple(self._validators[tool.name].iter_errors(event.action.arguments))
        if errors:
            return self._decision(Outcome.DENY, action_hash, (), ("invalid_arguments",))
        violated_limit = self._violated_limit(event, session)
        if violated_limit is not None:
            return self._decision(
                Outcome.DENY,
                action_hash,
                (),
                (f"limit:{violated_limit.id}",),
            )
        matched = tuple(rule for rule in self.policy.rules if self._matches(rule, event, session))
        denied = tuple(rule for rule in matched if rule.effect is Outcome.DENY)
        approvals = tuple(rule for rule in matched if rule.effect is Outcome.REQUIRE_APPROVAL)
        allowed = tuple(rule for rule in matched if rule.effect is Outcome.ALLOW)
        ordered = (*denied, *approvals, *allowed)
        matched_ids = tuple(rule.id for rule in ordered)
        if denied:
            return self._decision(
                Outcome.DENY,
                action_hash,
                matched_ids,
                tuple(rule.reason for rule in denied),
            )
        if approvals:
            return self._decision(
                Outcome.REQUIRE_APPROVAL,
                action_hash,
                matched_ids,
                tuple(rule.reason for rule in approvals),
            )
        if allowed:
            return self._decision(
                Outcome.ALLOW,
                action_hash,
                matched_ids,
                tuple(rule.reason for rule in allowed),
            )
        return self._decision(Outcome.DENY, action_hash, (), ("unmatched",))

    @staticmethod
    def _invalid_context(event: Event, session: SessionSnapshot) -> str | None:
        identifiers = (event.event_id, event.session_id, event.principal.id, event.action.tool)
        if not all(isinstance(value, str) and value for value in identifiers):
            return "invalid_event_context"
        tenant = event.principal.tenant
        if tenant is not None and (not isinstance(tenant, str) or not tenant):
            return "invalid_event_context"
        if not isinstance(event.principal.roles, tuple) or not all(
            isinstance(role, str) and role for role in event.principal.roles
        ):
            return "invalid_event_context"
        if not isinstance(event.labels, dict) or not all(
            isinstance(field, str)
            and field
            and isinstance(labels, frozenset)
            and all(isinstance(label, str) and label for label in labels)
            for field, labels in event.labels.items()
        ):
            return "invalid_event_context"
        if not isinstance(event.provenance, dict) or not all(
            isinstance(field, str)
            and field
            and isinstance(sources, tuple)
            and all(isinstance(source, str) and source for source in sources)
            for field, sources in event.provenance.items()
        ):
            return "invalid_event_context"
        if not isinstance(session.call_counts, dict) or not all(
            isinstance(tool, str)
            and tool
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
            for tool, count in session.call_counts.items()
        ):
            return "invalid_session_state"
        if not isinstance(session.sums, dict) or not all(
            isinstance(limit, str)
            and limit
            and isinstance(total, (int, float))
            and not isinstance(total, bool)
            and math.isfinite(total)
            and total >= 0
            for limit, total in session.sums.items()
        ):
            return "invalid_session_state"
        return None

    def action_hash(self, event: Event) -> str:
        return digest_json(
            {
                "policy_hash": self.policy.policy_hash,
                "session_id": event.session_id,
                "principal": {
                    "id": event.principal.id,
                    "tenant": event.principal.tenant,
                    "roles": event.principal.roles,
                },
                "action": {
                    "tool": event.action.tool,
                    "arguments": event.action.arguments,
                },
                "labels": {field: sorted(labels) for field, labels in event.labels.items()},
                "provenance": event.provenance,
            }
        )

    def reservations(self, event: Event) -> tuple[tuple[Limit, float], ...]:
        reservations: list[tuple[Limit, float]] = []
        for limit in self.policy.limits:
            if limit.tool != event.action.tool:
                continue
            reservations.append((limit, self._limit_amount(limit, event)))
        return tuple(reservations)

    def _decision(
        self,
        outcome: Outcome,
        action_hash: str,
        matched_rules: tuple[str, ...],
        reason_codes: tuple[str, ...],
    ) -> Decision:
        decision_id = digest_json(
            {
                "policy_hash": self.policy.policy_hash,
                "action_hash": action_hash,
                "outcome": outcome,
                "matched_rules": matched_rules,
                "reason_codes": reason_codes,
            }
        )
        return Decision(
            decision_id=decision_id,
            outcome=outcome,
            policy_hash=self.policy.policy_hash,
            action_hash=action_hash,
            matched_rules=matched_rules,
            reason_codes=reason_codes,
        )

    def _violated_limit(self, event: Event, session: SessionSnapshot) -> Limit | None:
        for limit, amount in self.reservations(event):
            if limit.kind == "count":
                current = float(session.call_counts.get(limit.tool, 0))
            else:
                current = session.sums.get(limit.id, 0.0)
            if current + amount > limit.maximum:
                return limit
        return None

    @staticmethod
    def _limit_amount(limit: Limit, event: Event) -> float:
        if limit.kind == "count":
            return 1.0
        value = event.action.arguments.get(limit.argument or "")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            return float("inf")
        return float(value)

    def _matches(self, rule: Rule, event: Event, session: SessionSnapshot) -> bool:
        return all(
            self._matches_condition(condition, event, session) for condition in rule.conditions
        )

    def _matches_condition(
        self, condition: Condition, event: Event, session: SessionSnapshot
    ) -> bool:
        if condition.operator == "has_label":
            return condition.expected in event.labels.get(condition.field, frozenset())
        if condition.operator == "derived_from":
            return condition.expected in event.provenance.get(condition.field, ())
        actual = self._resolve_field(condition.field, event, session)
        if actual is _MISSING:
            return False
        if condition.operator == "eq":
            return actual == condition.expected
        if condition.operator == "neq":
            return actual != condition.expected
        if condition.operator == "in":
            return actual in condition.expected
        if condition.operator == "not_in":
            return actual not in condition.expected
        if condition.operator in {"lte", "gte"}:
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return False
            if condition.operator == "lte":
                return actual <= condition.expected
            return actual >= condition.expected
        return False

    def _resolve_field(self, field: str, event: Event, session: SessionSnapshot) -> Any:
        tool = self.policy.tools.get(event.action.tool)
        fixed: dict[str, Any] = {
            "action.tool": event.action.tool,
            "principal.id": event.principal.id,
            "principal.tenant": event.principal.tenant,
            "principal.roles": event.principal.roles,
            "tool.risk": tool.risk if tool else _MISSING,
            "tool.sink": tool.sink if tool else _MISSING,
        }
        if field in fixed:
            return fixed[field]
        if field.startswith("action.arguments."):
            return _nested_value(event.action.arguments, field.removeprefix("action.arguments."))
        if field.startswith("session.call_count."):
            return session.call_counts.get(field.removeprefix("session.call_count."), 0)
        if field.startswith("session.sum."):
            return session.sums.get(field.removeprefix("session.sum."), 0.0)
        return _MISSING


def _nested_value(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current
