from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from railproof.engine import DecisionEngine
from railproof.exceptions import RailproofError
from railproof.policy import load_policy
from railproof.replay import event_from_dict, replay_cases, session_from_dict


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="railproof")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="compile and validate a policy")
    validate.add_argument("policy", type=Path)

    check = subparsers.add_parser("check", help="evaluate one event from a JSON file")
    check.add_argument("policy", type=Path)
    check.add_argument("event", type=Path)

    replay = subparsers.add_parser("replay", help="run JSONL decision fixtures")
    replay.add_argument("policy", type=Path)
    replay.add_argument("fixtures", type=Path)
    return parser


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        policy = load_policy(args.policy)
        if args.command == "validate":
            _print({"policy_hash": policy.policy_hash, "status": "valid"})
            return 0
        if args.command == "check":
            raw = json.loads(args.event.read_text(encoding="utf-8"))
            event = event_from_dict(raw.get("event", raw))
            session = session_from_dict(raw.get("session"))
            decision = DecisionEngine(policy).decide(event, session)
            _print(asdict(decision))
            return 0 if decision.outcome != "error" else 2
        report = replay_cases(policy, args.fixtures)
        _print(asdict(report))
        replay_status = 0 if report.failed == 0 else 1
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        RailproofError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 2
    else:
        return replay_status


if __name__ == "__main__":
    raise SystemExit(main())
