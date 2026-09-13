from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from railproof.canonical import canonical_json
from railproof.exceptions import AdapterError, CanonicalizationError
from railproof.models import Action, Event, Principal


def event_from_mcp_request(
    request: Mapping[str, Any],
    *,
    principal: Principal,
    session_id: str,
    labels: Mapping[str, set[str] | frozenset[str]] | None = None,
    provenance: Mapping[str, tuple[str, ...] | list[str]] | None = None,
) -> Event:
    if request.get("jsonrpc") != "2.0" or request.get("method") != "tools/call":
        raise AdapterError("MCP request must be a JSON-RPC 2.0 tools/call request")
    params = request.get("params")
    if not isinstance(params, Mapping):
        raise AdapterError("MCP tools/call params must be an object")
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or not name:
        raise AdapterError("MCP tool name must be a non-empty string")
    if not isinstance(arguments, dict):
        raise AdapterError("MCP tool arguments must be an object")
    try:
        request_id = canonical_json(request.get("id"))
    except CanonicalizationError as error:
        raise AdapterError("MCP request id is not canonical JSON") from error
    return Event(
        event_id=f"mcp:{request_id}",
        session_id=session_id,
        stage="before_tool",
        principal=principal,
        action=Action(tool=name, arguments=arguments),
        labels={field: frozenset(values) for field, values in (labels or {}).items()},
        provenance={field: tuple(values) for field, values in (provenance or {}).items()},
    )
