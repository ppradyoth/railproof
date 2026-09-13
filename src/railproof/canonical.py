from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from railproof.exceptions import CanonicalizationError

MAX_DEPTH = 64


def _normalize(value: Any, *, seen: set[int], depth: int) -> Any:
    if depth > MAX_DEPTH:
        raise CanonicalizationError(f"canonical JSON exceeds maximum depth of {MAX_DEPTH}")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError("non-finite numbers are not canonical JSON")
        return value
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in seen:
            raise CanonicalizationError("canonical JSON contains a cycle")
        seen.add(identity)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise CanonicalizationError("canonical JSON object keys must be strings")
                normalized[key] = _normalize(item, seen=seen, depth=depth + 1)
            return normalized
        finally:
            seen.remove(identity)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        identity = id(value)
        if identity in seen:
            raise CanonicalizationError("canonical JSON contains a cycle")
        seen.add(identity)
        try:
            return [_normalize(item, seen=seen, depth=depth + 1) for item in value]
        finally:
            seen.remove(identity)
    raise CanonicalizationError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            _normalize(value, seen=set(), depth=0),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise CanonicalizationError(str(error)) from error


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
