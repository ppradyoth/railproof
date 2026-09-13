import json
from pathlib import Path

from railproof.policy import CompiledPolicy
from railproof.replay import replay_cases


def test_replay_reports_expected_and_actual_decisions(
    policy: CompiledPolicy, tmp_path: Path
) -> None:
    fixture = tmp_path / "cases.jsonl"
    cases = [
        {
            "id": "allow-weather",
            "event": {
                "event_id": "evt_1",
                "session_id": "session_1",
                "stage": "before_tool",
                "principal": {"id": "user_1", "tenant": "tenant_a"},
                "action": {"tool": "get_weather", "arguments": {"city": "Bengaluru"}},
            },
            "expected": "allow",
        },
        {
            "id": "deny-unknown",
            "event": {
                "event_id": "evt_2",
                "session_id": "session_2",
                "stage": "before_tool",
                "principal": {"id": "user_1", "tenant": "tenant_a"},
                "action": {"tool": "delete_database", "arguments": {}},
            },
            "expected": "deny",
        },
    ]
    fixture.write_text("\n\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")

    report = replay_cases(policy, fixture)

    assert report.total == 2
    assert report.passed == 2
    assert report.failed == 0


def test_replay_uses_line_number_when_id_is_missing(policy: CompiledPolicy, tmp_path: Path) -> None:
    fixture = tmp_path / "cases.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "event": {
                    "event_id": "evt_1",
                    "session_id": "session_1",
                    "stage": "before_tool",
                    "principal": {"id": "user_1"},
                    "action": {"tool": "get_weather", "arguments": {"city": "Bengaluru"}},
                },
                "expected": "deny",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = replay_cases(policy, fixture)
    assert report.results[0].id == "line-1"
    assert report.failed == 1
