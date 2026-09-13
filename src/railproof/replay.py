from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from railproof.engine import DecisionEngine
from railproof.models import Action, Event, Outcome, Principal, SessionSnapshot

if TYPE_CHECKING:
    from railproof.policy import CompiledPolicy


@dataclass(frozen=True, slots=True)
class ReplayResult:
    id: str
    expected: Outcome
    actual: Outcome
    decision_id: str
    passed: bool


@dataclass(frozen=True, slots=True)
class ReplayReport:
    total: int
    passed: int
    failed: int
    results: tuple[ReplayResult, ...]


def event_from_dict(value: dict[str, Any]) -> Event:
    principal = value["principal"]
    action = value["action"]
    return Event(
        event_id=str(value["event_id"]),
        session_id=str(value["session_id"]),
        stage=str(value["stage"]),
        principal=Principal(
            id=str(principal["id"]),
            tenant=principal.get("tenant"),
            roles=tuple(principal.get("roles", [])),
        ),
        action=Action(tool=str(action["tool"]), arguments=dict(action["arguments"])),
        labels={field: frozenset(labels) for field, labels in value.get("labels", {}).items()},
        provenance={
            field: tuple(sources) for field, sources in value.get("provenance", {}).items()
        },
    )


def session_from_dict(value: dict[str, Any] | None) -> SessionSnapshot:
    if value is None:
        return SessionSnapshot()
    return SessionSnapshot(
        call_counts={name: int(count) for name, count in value.get("call_counts", {}).items()},
        sums={name: float(total) for name, total in value.get("sums", {}).items()},
    )


def replay_cases(policy: CompiledPolicy, path: str | Path) -> ReplayReport:
    engine = DecisionEngine(policy)
    results: list[ReplayResult] = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            case = json.loads(line)
            case_id = str(case.get("id", f"line-{line_number}"))
            expected = Outcome(case["expected"])
            event = event_from_dict(case["event"])
            session = session_from_dict(case.get("session"))
            decision = engine.decide(event, session)
            results.append(
                ReplayResult(
                    id=case_id,
                    expected=expected,
                    actual=decision.outcome,
                    decision_id=decision.decision_id,
                    passed=decision.outcome is expected,
                )
            )
    passed = sum(result.passed for result in results)
    return ReplayReport(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=tuple(results),
    )
