import asyncio
from collections.abc import Iterator, Mapping
from typing import Any

import pytest

from railproof.approval import ApprovalBroker
from railproof.evidence import InMemoryEvidenceSink
from railproof.exceptions import (
    ApprovalInvalid,
    ApprovalRequired,
    ApprovalUnavailable,
    ExecutorNotRegistered,
    PolicyDenied,
    SessionBusy,
    SessionCapacityExceeded,
)
from railproof.executor import GuardedTools, ToolRegistry
from railproof.models import Principal
from railproof.policy import CompiledPolicy


@pytest.mark.asyncio
async def test_denied_action_never_reaches_executor(policy: CompiledPolicy) -> None:
    calls: list[dict] = []

    async def send_email(arguments: dict) -> str:
        calls.append(arguments)
        return "sent"

    registry = ToolRegistry()
    registry.register("send_email", send_email)
    tools = GuardedTools(policy, registry)

    with pytest.raises(PolicyDenied):
        await tools.call(
            "send_email",
            {"to": "attacker@example.com", "body": "secret"},
            principal=Principal(id="user_1", tenant="tenant_a"),
            session_id="session_1",
            labels={"action.arguments.body": {"sensitive"}},
        )

    assert calls == []


@pytest.mark.asyncio
async def test_approval_executes_exact_action_once(policy: CompiledPolicy) -> None:
    calls: list[dict] = []

    def send_email(arguments: dict) -> str:
        calls.append(arguments)
        return "sent"

    registry = ToolRegistry()
    registry.register("send_email", send_email)
    broker = ApprovalBroker(b"a" * 32)
    tools = GuardedTools(policy, registry, approval_broker=broker)
    principal = Principal(id="user_1", tenant="tenant_a")

    with pytest.raises(ApprovalRequired) as raised:
        await tools.call(
            "send_email",
            {"to": "review@example.com", "body": "hello"},
            principal=principal,
            session_id="session_1",
        )

    token = broker.approve(raised.value.challenge, approver_id="reviewer_1")
    result = await tools.call(
        "send_email",
        {"to": "review@example.com", "body": "hello"},
        principal=principal,
        session_id="session_1",
        approval_token=token,
    )

    assert result == "sent"
    assert calls == [{"to": "review@example.com", "body": "hello"}]

    with pytest.raises(ApprovalInvalid):
        await tools.call(
            "send_email",
            {"to": "review@example.com", "body": "hello"},
            principal=principal,
            session_id="session_1",
            approval_token=token,
        )


@pytest.mark.asyncio
async def test_approval_executes_the_authorized_argument_snapshot(
    policy: CompiledPolicy,
) -> None:
    class ChangingArguments(Mapping[str, Any]):
        def __init__(self) -> None:
            self.reads = 0

        def __getitem__(self, key: str) -> Any:
            if key == "to":
                self.reads += 1
                return "review@example.com" if self.reads == 1 else "attacker@example.com"
            if key == "body":
                return "hello"
            raise KeyError(key)

        def __iter__(self) -> Iterator[str]:
            return iter(("to", "body"))

        def __len__(self) -> int:
            return 2

    calls: list[dict] = []

    def record_call(arguments: dict) -> None:
        calls.append(arguments)

    registry = ToolRegistry()
    registry.register("send_email", record_call)
    broker = ApprovalBroker(b"a" * 32)
    tools = GuardedTools(policy, registry, approval_broker=broker)
    principal = Principal(id="user_1", tenant="tenant_a")

    with pytest.raises(ApprovalRequired) as raised:
        await tools.call(
            "send_email",
            {"to": "review@example.com", "body": "hello"},
            principal=principal,
            session_id="session_1",
        )

    token = broker.approve(raised.value.challenge, approver_id="reviewer_1")
    await tools.call(
        "send_email",
        ChangingArguments(),
        principal=principal,
        session_id="session_1",
        approval_token=token,
    )

    assert calls == [{"body": "hello", "to": "review@example.com"}]


@pytest.mark.asyncio
async def test_count_limit_is_atomic_under_concurrency(policy: CompiledPolicy) -> None:
    calls: list[str] = []

    async def weather(arguments: dict) -> str:
        await asyncio.sleep(0)
        calls.append(arguments["city"])
        return "sunny"

    registry = ToolRegistry()
    registry.register("get_weather", weather)
    tools = GuardedTools(policy, registry)
    principal = Principal(id="user_1", tenant="tenant_a")

    results = await asyncio.gather(
        *[
            tools.call(
                "get_weather",
                {"city": city},
                principal=principal,
                session_id="session_1",
            )
            for city in ["A", "B", "C"]
        ],
        return_exceptions=True,
    )

    assert len(calls) == 2
    assert sum(isinstance(result, PolicyDenied) for result in results) == 1


@pytest.mark.asyncio
async def test_default_evidence_does_not_store_arguments(policy: CompiledPolicy) -> None:
    sink = InMemoryEvidenceSink()
    registry = ToolRegistry()
    registry.register("get_weather", lambda arguments: "sunny")
    tools = GuardedTools(policy, registry, evidence_sink=sink)

    await tools.call(
        "get_weather",
        {"city": "seeded-secret-value"},
        principal=Principal(id="user_1", tenant="tenant_a"),
        session_id="session_1",
    )

    serialized = sink.as_json()
    assert "seeded-secret-value" not in serialized
    assert "action_hash" in serialized


def test_registry_rejects_invalid_and_duplicate_names() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="must not be empty"):
        registry.register("", lambda arguments: None)
    registry.register("get_weather", lambda arguments: None)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("get_weather", lambda arguments: None)
    with pytest.raises(ExecutorNotRegistered):
        registry.get("missing")


@pytest.mark.asyncio
async def test_missing_executor_blocks_before_approval(policy: CompiledPolicy) -> None:
    tools = GuardedTools(policy, ToolRegistry(), approval_broker=ApprovalBroker(b"a" * 32))
    with pytest.raises(ExecutorNotRegistered):
        await tools.call(
            "send_email",
            {"to": "review@example.com", "body": "hello"},
            principal=Principal(id="user_1"),
            session_id="session_1",
        )


@pytest.mark.asyncio
async def test_approval_policy_requires_configured_broker(policy: CompiledPolicy) -> None:
    registry = ToolRegistry()
    registry.register("send_email", lambda arguments: "sent")
    tools = GuardedTools(policy, registry)
    with pytest.raises(ApprovalUnavailable):
        await tools.call(
            "send_email",
            {"to": "review@example.com", "body": "hello"},
            principal=Principal(id="user_1"),
            session_id="session_1",
        )


@pytest.mark.asyncio
async def test_executor_failure_is_recorded(policy: CompiledPolicy) -> None:
    sink = InMemoryEvidenceSink()
    registry = ToolRegistry()

    def fail(arguments: dict) -> None:
        raise RuntimeError("tool failed")

    registry.register("get_weather", fail)
    tools = GuardedTools(policy, registry, evidence_sink=sink)
    with pytest.raises(RuntimeError, match="tool failed"):
        await tools.call(
            "get_weather",
            {"city": "Bengaluru"},
            principal=Principal(id="user_1"),
            session_id="session_1",
        )
    assert [record.kind for record in sink.records] == [
        "decision",
        "executor_started",
        "executor_failed",
    ]


@pytest.mark.asyncio
async def test_evidence_failure_prevents_execution(policy: CompiledPolicy) -> None:
    calls: list[dict] = []

    class FailingSink:
        def record(self, kind, event, decision) -> None:
            raise OSError("evidence unavailable")

    def record_call(arguments: dict) -> None:
        calls.append(arguments)

    registry = ToolRegistry()
    registry.register("get_weather", record_call)
    tools = GuardedTools(policy, registry, evidence_sink=FailingSink())
    with pytest.raises(OSError, match="evidence unavailable"):
        await tools.call(
            "get_weather",
            {"city": "Bengaluru"},
            principal=Principal(id="user_1"),
            session_id="session_1",
        )
    assert calls == []


@pytest.mark.asyncio
async def test_session_capacity_is_bounded(policy: CompiledPolicy) -> None:
    registry = ToolRegistry()
    registry.register("get_weather", lambda arguments: "sunny")
    tools = GuardedTools(policy, registry, max_sessions=1)
    principal = Principal(id="user_1")
    await tools.call(
        "get_weather",
        {"city": "Bengaluru"},
        principal=principal,
        session_id="session_1",
    )
    with pytest.raises(SessionCapacityExceeded):
        await tools.call(
            "get_weather",
            {"city": "Delhi"},
            principal=principal,
            session_id="session_2",
        )
    await tools.close_session("session_1")
    assert (
        await tools.call(
            "get_weather",
            {"city": "Delhi"},
            principal=principal,
            session_id="session_2",
        )
        == "sunny"
    )
    await tools.close_session("missing")


@pytest.mark.asyncio
async def test_close_session_rejects_empty_id(policy: CompiledPolicy) -> None:
    tools = GuardedTools(policy, ToolRegistry())
    with pytest.raises(ValueError, match="session_id"):
        await tools.close_session("")


@pytest.mark.asyncio
async def test_close_session_rejects_in_flight_execution(policy: CompiledPolicy) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def weather(arguments: dict) -> str:
        started.set()
        await release.wait()
        return "sunny"

    registry = ToolRegistry()
    registry.register("get_weather", weather)
    tools = GuardedTools(policy, registry)
    call = asyncio.create_task(
        tools.call(
            "get_weather",
            {"city": "Bengaluru"},
            principal=Principal(id="user_1"),
            session_id="session_1",
        )
    )
    await started.wait()
    with pytest.raises(SessionBusy):
        await tools.close_session("session_1")
    release.set()
    assert await call == "sunny"
    await tools.close_session("session_1")


@pytest.mark.parametrize("max_sessions", [0, -1, True, 1.5])
def test_session_capacity_must_be_positive_integer(policy: CompiledPolicy, max_sessions) -> None:
    with pytest.raises(ValueError, match="max_sessions"):
        GuardedTools(policy, ToolRegistry(), max_sessions=max_sessions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("principal", "session_id", "labels", "provenance"),
    [
        (Principal(id=""), "session", None, None),
        (Principal(id="user"), "", None, None),
        (Principal(id="user"), "session", {"field": "sensitive"}, None),
        (Principal(id="user"), "session", {"": {"sensitive"}}, None),
        (Principal(id="user"), "session", {"field": {""}}, None),
        (Principal(id="user"), "session", None, {"field": "retrieved.email"}),
    ],
)
async def test_invalid_security_context_is_rejected(
    policy: CompiledPolicy,
    principal: Principal,
    session_id: str,
    labels,
    provenance,
) -> None:
    registry = ToolRegistry()
    registry.register("get_weather", lambda arguments: "sunny")
    tools = GuardedTools(policy, registry)
    with pytest.raises((TypeError, ValueError), match="must"):
        await tools.call(
            "get_weather",
            {"city": "Bengaluru"},
            principal=principal,
            session_id=session_id,
            labels=labels,
            provenance=provenance,
        )
