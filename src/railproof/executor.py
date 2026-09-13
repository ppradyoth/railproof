from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from railproof.canonical import canonical_json
from railproof.engine import DecisionEngine
from railproof.evidence import EvidenceSink, InMemoryEvidenceSink
from railproof.exceptions import (
    ApprovalRequired,
    ApprovalUnavailable,
    ExecutorNotRegistered,
    PolicyDenied,
    SessionBusy,
    SessionCapacityExceeded,
)
from railproof.models import Action, Event, Outcome, Principal, SessionSnapshot

if TYPE_CHECKING:
    from railproof.approval import ApprovalBroker
    from railproof.policy import CompiledPolicy

ToolExecutor = Callable[[dict[str, Any]], Any | Awaitable[Any]]
MAX_SESSIONS = 10_000


class ToolRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, ToolExecutor] = {}

    def register(self, name: str, executor: ToolExecutor) -> None:
        if not name:
            raise ValueError("tool name must not be empty")
        if name in self._executors:
            raise ValueError(f"tool executor is already registered: {name}")
        self._executors[name] = executor

    def get(self, name: str) -> ToolExecutor:
        try:
            return self._executors[name]
        except KeyError as error:
            raise ExecutorNotRegistered(f"tool executor is not registered: {name}") from error


@dataclass(slots=True)
class _SessionState:
    call_counts: dict[str, int] = field(default_factory=dict)
    sums: dict[str, float] = field(default_factory=dict)
    in_flight: int = 0

    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(call_counts=dict(self.call_counts), sums=dict(self.sums))


class GuardedTools:
    def __init__(
        self,
        policy: CompiledPolicy,
        registry: ToolRegistry,
        *,
        approval_broker: ApprovalBroker | None = None,
        evidence_sink: EvidenceSink | None = None,
        max_sessions: int = MAX_SESSIONS,
    ) -> None:
        if not isinstance(max_sessions, int) or isinstance(max_sessions, bool) or max_sessions <= 0:
            raise ValueError("max_sessions must be a positive integer")
        self.policy = policy
        self.registry = registry
        self.engine = DecisionEngine(policy)
        self.approval_broker = approval_broker
        self.evidence_sink = evidence_sink if evidence_sink is not None else InMemoryEvidenceSink()
        self.max_sessions = max_sessions
        self._states: dict[str, _SessionState] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_index_guard = asyncio.Lock()

    async def call(
        self,
        tool: str,
        arguments: Mapping[str, Any],
        *,
        principal: Principal,
        session_id: str,
        labels: Mapping[str, set[str] | frozenset[str]] | None = None,
        provenance: Mapping[str, tuple[str, ...] | list[str]] | None = None,
        approval_token: str | None = None,
    ) -> Any:
        if not session_id:
            raise ValueError("session_id must not be empty")
        if not principal.id:
            raise ValueError("principal id must not be empty")
        event_arguments, execution_arguments = _snapshot_arguments(arguments)
        event = Event(
            event_id=f"evt_{uuid.uuid4().hex}",
            session_id=session_id,
            stage="before_tool",
            principal=principal,
            action=Action(tool=tool, arguments=event_arguments),
            labels=_normalize_labels(labels),
            provenance=_normalize_provenance(provenance),
        )
        session_lock = await self._session_lock(session_id)
        async with session_lock:
            state = self._states.setdefault(session_id, _SessionState())
            decision = self.engine.decide(event, state.snapshot())
            self.evidence_sink.record("decision", event, decision)
            if decision.outcome is Outcome.DENY:
                raise PolicyDenied(decision)
            executor = self.registry.get(tool)
            if decision.outcome is Outcome.REQUIRE_APPROVAL:
                broker = self.approval_broker
                if broker is None:
                    raise ApprovalUnavailable(
                        "policy requires approval but no broker is configured"
                    )
                if approval_token is None:
                    challenge = broker.challenge(
                        action_hash=decision.action_hash,
                        policy_hash=decision.policy_hash,
                        principal=principal,
                    )
                    raise ApprovalRequired(decision, challenge)
                broker.verify(
                    approval_token,
                    action_hash=decision.action_hash,
                    policy_hash=decision.policy_hash,
                    principal=principal,
                )
                self.evidence_sink.record("approval_verified", event, decision)
            self._reserve(event, state)
            state.in_flight += 1
        try:
            self.evidence_sink.record("executor_started", event, decision)
            try:
                result = executor(execution_arguments)
                if inspect.isawaitable(result):
                    result = await result
            except Exception:
                self.evidence_sink.record("executor_failed", event, decision)
                raise
            self.evidence_sink.record("executor_completed", event, decision)
            return result
        finally:
            async with session_lock:
                state.in_flight -= 1

    async def _session_lock(self, session_id: str) -> asyncio.Lock:
        async with self._lock_index_guard:
            existing = self._locks.get(session_id)
            if existing is not None:
                return existing
            if len(self._locks) >= self.max_sessions:
                raise SessionCapacityExceeded("maximum active session capacity reached")
            session_lock = asyncio.Lock()
            self._locks[session_id] = session_lock
            return session_lock

    async def close_session(self, session_id: str) -> None:
        if not session_id:
            raise ValueError("session_id must not be empty")
        async with self._lock_index_guard:
            session_lock = self._locks.get(session_id)
            if session_lock is None:
                return
            async with session_lock:
                state = self._states.get(session_id)
                if state is not None and state.in_flight:
                    raise SessionBusy("session has in-flight tool executions")
                self._states.pop(session_id, None)
                self._locks.pop(session_id, None)

    def _reserve(self, event: Event, state: _SessionState) -> None:
        state.call_counts[event.action.tool] = state.call_counts.get(event.action.tool, 0) + 1
        for limit, amount in self.engine.reservations(event):
            if limit.kind == "sum":
                state.sums[limit.id] = state.sums.get(limit.id, 0.0) + amount


def _validate_string_collections(
    values: Mapping[str, set[str] | frozenset[str] | tuple[str, ...] | list[str]] | None,
    *,
    name: str,
) -> dict[str, tuple[str, ...]]:
    normalized: dict[str, tuple[str, ...]] = {}
    for field_name, items in (values or {}).items():
        if not isinstance(field_name, str) or not field_name:
            raise ValueError(f"{name} field names must be non-empty strings")
        if isinstance(items, (str, bytes)) or not isinstance(items, (set, frozenset, tuple, list)):
            raise TypeError(f"{name}.{field_name} must be a collection of strings")
        if not all(isinstance(item, str) and item for item in items):
            raise ValueError(f"{name}.{field_name} must contain non-empty strings")
        normalized[field_name] = tuple(items)
    return normalized


def _snapshot_arguments(
    arguments: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(arguments, Mapping):
        raise TypeError("arguments must be a mapping")
    encoded = canonical_json(arguments)
    event_arguments = json.loads(encoded)
    execution_arguments = json.loads(encoded)
    if not isinstance(event_arguments, dict) or not isinstance(execution_arguments, dict):
        raise TypeError("arguments must be a mapping")
    return event_arguments, execution_arguments


def _normalize_labels(
    values: Mapping[str, set[str] | frozenset[str]] | None,
) -> dict[str, frozenset[str]]:
    return {
        field_name: frozenset(items)
        for field_name, items in _validate_string_collections(values, name="labels").items()
    }


def _normalize_provenance(
    values: Mapping[str, tuple[str, ...] | list[str]] | None,
) -> dict[str, tuple[str, ...]]:
    return _validate_string_collections(values, name="provenance")
