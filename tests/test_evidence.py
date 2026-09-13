import json
from pathlib import Path

import pytest

from railproof.engine import DecisionEngine
from railproof.evidence import InMemoryEvidenceSink, JsonlEvidenceSink, make_record
from railproof.models import Action, Event, Principal, SessionSnapshot
from railproof.policy import CompiledPolicy


def test_evidence_hashes_principal_and_jsonl_appends(
    policy: CompiledPolicy, tmp_path: Path
) -> None:
    event = Event(
        event_id="evt_1",
        session_id="session_1",
        stage="before_tool",
        principal=Principal(id="private-user", tenant="tenant_a"),
        action=Action(tool="get_weather", arguments={"city": "Bengaluru"}),
    )
    decision = DecisionEngine(policy).decide(event, SessionSnapshot())
    record = make_record("decision", event, decision)
    assert record.principal_hash != "private-user"

    path = tmp_path / "evidence.jsonl"
    sink = JsonlEvidenceSink(path)
    sink.record("decision", event, decision)
    sink.record("executor_completed", event, decision)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["kind"] for row in rows] == ["decision", "executor_completed"]
    assert "private-user" not in path.read_text(encoding="utf-8")


def test_in_memory_evidence_is_bounded(policy: CompiledPolicy) -> None:
    event = Event(
        event_id="evt_1",
        session_id="session_1",
        stage="before_tool",
        principal=Principal(id="user_1"),
        action=Action(tool="get_weather", arguments={"city": "Bengaluru"}),
    )
    decision = DecisionEngine(policy).decide(event, SessionSnapshot())
    sink = InMemoryEvidenceSink(max_records=1)
    sink.record("first", event, decision)
    sink.record("second", event, decision)
    assert [record.kind for record in sink.records] == ["second"]

    with pytest.raises(ValueError, match="max_records"):
        InMemoryEvidenceSink(max_records=0)
