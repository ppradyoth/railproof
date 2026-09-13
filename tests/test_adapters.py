import pytest

from railproof.adapters.mcp import event_from_mcp_request
from railproof.adapters.openai import event_from_openai_tool_call
from railproof.engine import DecisionEngine
from railproof.exceptions import AdapterError
from railproof.models import Outcome, Principal, SessionSnapshot
from railproof.policy import CompiledPolicy


def test_openai_adapter_normalizes_function_call() -> None:
    event = event_from_openai_tool_call(
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"city":"Bengaluru"}',
            },
        },
        principal=Principal(id="user_1", tenant="tenant_a"),
        session_id="session_1",
    )

    assert event.action.tool == "get_weather"
    assert event.action.arguments == {"city": "Bengaluru"}


def test_mcp_adapter_normalizes_tools_call() -> None:
    event = event_from_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_weather", "arguments": {"city": "Bengaluru"}},
        },
        principal=Principal(id="user_1", tenant="tenant_a"),
        session_id="session_1",
    )

    assert event.action.tool == "get_weather"
    assert event.action.arguments == {"city": "Bengaluru"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": "", "type": "function", "function": {"name": "tool", "arguments": "{}"}},
        {"id": "call_1", "type": "custom", "function": {"name": "tool", "arguments": "{}"}},
        {"id": "call_1", "type": "function", "function": []},
        {"id": "call_1", "type": "function", "function": {"name": "", "arguments": "{}"}},
        {"id": "call_1", "type": "function", "function": {"name": "tool", "arguments": {}}},
        {"id": "call_1", "type": "function", "function": {"name": "tool", "arguments": "{"}},
        {"id": "call_1", "type": "function", "function": {"name": "tool"}},
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "tool", "arguments": "[]"},
        },
    ],
)
def test_openai_adapter_fails_closed(payload) -> None:
    with pytest.raises(AdapterError):
        event_from_openai_tool_call(
            payload,
            principal=Principal(id="user_1", tenant="tenant_a"),
            session_id="session_1",
        )


def test_mcp_adapter_rejects_non_tool_method() -> None:
    with pytest.raises(AdapterError, match="tools/call"):
        event_from_mcp_request(
            {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {}},
            principal=Principal(id="user_1", tenant="tenant_a"),
            session_id="session_1",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": []},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": ""}},
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "tool", "arguments": []},
        },
        {"jsonrpc": "2.0", "id": float("nan"), "method": "tools/call", "params": {"name": "tool"}},
    ],
)
def test_mcp_adapter_fails_closed(payload) -> None:
    with pytest.raises(AdapterError):
        event_from_mcp_request(
            payload,
            principal=Principal(id="user_1", tenant="tenant_a"),
            session_id="session_1",
        )


def test_openai_and_mcp_adapters_produce_equivalent_decisions(
    policy: CompiledPolicy,
) -> None:
    principal = Principal(id="user_1", tenant="tenant_a")
    openai_event = event_from_openai_tool_call(
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"city":"Bengaluru"}'},
        },
        principal=principal,
        session_id="session_1",
    )
    mcp_event = event_from_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_weather", "arguments": {"city": "Bengaluru"}},
        },
        principal=principal,
        session_id="session_1",
    )
    engine = DecisionEngine(policy)
    assert engine.decide(openai_event, SessionSnapshot()).outcome is Outcome.ALLOW
    assert engine.decide(mcp_event, SessionSnapshot()).outcome is Outcome.ALLOW
