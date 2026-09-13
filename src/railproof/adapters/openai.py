from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from railproof.exceptions import AdapterError
from railproof.models import Action, Event, Principal


def event_from_openai_tool_call(
    tool_call: Mapping[str, Any],
    *,
    principal: Principal,
    session_id: str,
    labels: Mapping[str, set[str] | frozenset[str]] | None = None,
    provenance: Mapping[str, tuple[str, ...] | list[str]] | None = None,
) -> Event:
    try:
        call_id = tool_call["id"]
        if not isinstance(call_id, str) or not call_id:
            raise AdapterError("OpenAI tool call id must be a non-empty string")
        if tool_call["type"] != "function":
            raise AdapterError("OpenAI tool call type must be function")
        function = tool_call["function"]
        if not isinstance(function, Mapping):
            raise AdapterError("OpenAI function must be an object")
        name = function["name"]
        arguments_text = function["arguments"]
        if not isinstance(name, str) or not name:
            raise AdapterError("OpenAI function name must be a non-empty string")
        if not isinstance(arguments_text, str):
            raise AdapterError("OpenAI function arguments must be a JSON string")
        arguments = json.loads(arguments_text)
        if not isinstance(arguments, dict):
            raise AdapterError("OpenAI function arguments must decode to an object")
    except AdapterError:
        raise
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise AdapterError("malformed OpenAI tool call") from error
    return Event(
        event_id=f"openai:{call_id}",
        session_id=session_id,
        stage="before_tool",
        principal=principal,
        action=Action(tool=name, arguments=arguments),
        labels={field: frozenset(values) for field, values in (labels or {}).items()},
        provenance={field: tuple(values) for field, values in (provenance or {}).items()},
    )
