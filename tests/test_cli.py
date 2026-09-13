import json
from pathlib import Path

from railproof.cli import main


def _event() -> dict:
    return {
        "event_id": "evt_1",
        "session_id": "session_1",
        "stage": "before_tool",
        "principal": {"id": "user_1", "roles": ["operator"]},
        "action": {"tool": "get_weather", "arguments": {"city": "Bengaluru"}},
    }


def test_validate_command(policy_path: Path, capsys) -> None:
    assert main(["validate", str(policy_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "valid"
    assert len(output["policy_hash"]) == 64


def test_check_command_accepts_wrapped_event(policy_path: Path, tmp_path: Path, capsys) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"event": _event(), "session": {}}), encoding="utf-8")
    assert main(["check", str(policy_path), str(event_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["outcome"] == "allow"


def test_replay_command_reports_failure(policy_path: Path, tmp_path: Path, capsys) -> None:
    fixture = tmp_path / "cases.jsonl"
    fixture.write_text(
        json.dumps({"id": "wrong-expectation", "event": _event(), "expected": "deny"}) + "\n",
        encoding="utf-8",
    )
    assert main(["replay", str(policy_path), str(fixture)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["failed"] == 1


def test_cli_returns_error_for_invalid_input(policy_path: Path, tmp_path: Path, capsys) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text("not-json", encoding="utf-8")
    assert main(["check", str(policy_path), str(event_path)]) == 2
    assert "Expecting value" in capsys.readouterr().err
