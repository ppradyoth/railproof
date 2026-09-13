from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from railproof.models import Decision, Event


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    timestamp: float
    kind: str
    event_id: str
    session_id: str
    principal_hash: str
    tool: str
    action_hash: str
    policy_hash: str
    decision_id: str
    outcome: str
    matched_rules: tuple[str, ...]
    reason_codes: tuple[str, ...]


class EvidenceSink(Protocol):
    def record(self, kind: str, event: Event, decision: Decision) -> None: ...


def make_record(kind: str, event: Event, decision: Decision) -> EvidenceRecord:
    principal_value = f"{event.principal.tenant or ''}\x00{event.principal.id}"
    return EvidenceRecord(
        timestamp=time.time(),
        kind=kind,
        event_id=event.event_id,
        session_id=event.session_id,
        principal_hash=hashlib.sha256(principal_value.encode()).hexdigest(),
        tool=event.action.tool,
        action_hash=decision.action_hash,
        policy_hash=decision.policy_hash,
        decision_id=decision.decision_id,
        outcome=decision.outcome,
        matched_rules=decision.matched_rules,
        reason_codes=decision.reason_codes,
    )


class InMemoryEvidenceSink:
    def __init__(self, *, max_records: int = 10_000) -> None:
        if not isinstance(max_records, int) or isinstance(max_records, bool) or max_records <= 0:
            raise ValueError("max_records must be a positive integer")
        self.records: deque[EvidenceRecord] = deque(maxlen=max_records)
        self._lock = threading.Lock()

    def record(self, kind: str, event: Event, decision: Decision) -> None:
        with self._lock:
            self.records.append(make_record(kind, event, decision))

    def as_json(self) -> str:
        with self._lock:
            records = tuple(self.records)
        return json.dumps([asdict(record) for record in records], sort_keys=True)


class JsonlEvidenceSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(self, kind: str, event: Event, decision: Decision) -> None:
        record: dict[str, Any] = asdict(make_record(kind, event, decision))
        serialized = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(serialized)
