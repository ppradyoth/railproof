from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
import yaml.resolver
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from yaml.events import AliasEvent

if TYPE_CHECKING:
    from yaml.nodes import MappingNode

from railproof.canonical import digest_json
from railproof.exceptions import CanonicalizationError, PolicyCompileError
from railproof.models import Outcome

API_VERSION = "railproof.dev/v1alpha1"
KIND = "AgentSecurityPolicy"
MAX_POLICY_BYTES = 1_048_576
MAX_YAML_ALIASES = 100
SUPPORTED_OPERATORS = frozenset(
    {
        "eq",
        "neq",
        "in",
        "not_in",
        "lte",
        "gte",
        "has_label",
        "derived_from",
    }
)
SUPPORTED_FIELDS = frozenset(
    {
        "action.tool",
        "principal.id",
        "principal.tenant",
        "principal.roles",
        "tool.risk",
        "tool.sink",
    }
)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    schema: dict[str, Any]
    risk: str
    sink: str


@dataclass(frozen=True, slots=True)
class Condition:
    field: str
    operator: str
    expected: Any


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    stage: str
    priority: int
    conditions: tuple[Condition, ...]
    effect: Outcome
    reason: str


@dataclass(frozen=True, slots=True)
class Limit:
    id: str
    tool: str
    kind: str
    maximum: float
    argument: str | None = None


@dataclass(frozen=True, slots=True)
class CompiledPolicy:
    policy_hash: str
    tools: dict[str, ToolDefinition]
    rules: tuple[Rule, ...]
    limits: tuple[Limit, ...]
    source: dict[str, Any]


class _UniqueKeyLoader(yaml.SafeLoader):
    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self._alias_count = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):
            self._alias_count += 1
            if self._alias_count > MAX_YAML_ALIASES:
                raise PolicyCompileError(
                    f"policy exceeds maximum YAML alias count of {MAX_YAML_ALIASES}"
                )
        return super().compose_node(parent, index)


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: MappingNode, *, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise PolicyCompileError("policy mapping keys must be hashable") from error
        if duplicate:
            raise PolicyCompileError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PolicyCompileError(f"{path} must be a mapping with string keys")
    return value


def _sequence(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise PolicyCompileError(f"{path} must be a list")
    return value


def _fields(
    value: dict[str, Any],
    *,
    allowed: set[str],
    required: set[str],
    path: str,
) -> None:
    unknown = set(value) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise PolicyCompileError(f"{path} has unknown field(s): {names}")
    missing = required - set(value)
    if missing:
        names = ", ".join(sorted(missing))
        raise PolicyCompileError(f"{path} is missing field(s): {names}")


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PolicyCompileError(f"{path} must be a non-empty string")
    return value


def _parse_tools(value: Any) -> dict[str, ToolDefinition]:
    raw_tools = _mapping(value, "tools")
    if not raw_tools:
        raise PolicyCompileError("tools must not be empty")
    tools: dict[str, ToolDefinition] = {}
    for name, candidate in raw_tools.items():
        path = f"tools.{name}"
        validated_name = _text(name, "tool name")
        raw = _mapping(candidate, path)
        _fields(
            raw,
            allowed={"schema", "risk", "sink"},
            required={"schema", "risk", "sink"},
            path=path,
        )
        schema = _mapping(raw["schema"], f"{path}.schema")
        _reject_refs(schema, f"{path}.schema")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise PolicyCompileError(f"{path} has invalid JSON Schema: {error.message}") from error
        tools[validated_name] = ToolDefinition(
            name=validated_name,
            schema=copy.deepcopy(schema),
            risk=_text(raw["risk"], f"{path}.risk"),
            sink=_text(raw["sink"], f"{path}.sink"),
        )
    return tools


def _reject_refs(value: Any, path: str) -> None:
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str):
            raise PolicyCompileError(f"{path} contains unsupported $ref: {reference}")
        for key, child in value.items():
            _reject_refs(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_refs(child, f"{path}[{index}]")


def _parse_condition(value: Any, path: str) -> Condition:
    raw = _mapping(value, path)
    _fields(
        raw,
        allowed={"field", "op", "value", "values"},
        required={"field", "op"},
        path=path,
    )
    field = _text(raw["field"], f"{path}.field")
    dynamic_prefixes = (
        "action.arguments.",
        "session.call_count.",
        "session.sum.",
    )
    if field not in SUPPORTED_FIELDS and not field.startswith(dynamic_prefixes):
        raise PolicyCompileError(f"{path}.field is unsupported: {field}")
    if field.endswith("."):
        raise PolicyCompileError(f"{path}.field is incomplete: {field}")
    operator = _text(raw["op"], f"{path}.op")
    if operator not in SUPPORTED_OPERATORS:
        raise PolicyCompileError(f"{path} uses unsupported operator: {operator}")
    if operator in {"in", "not_in"}:
        if "value" in raw or "values" not in raw:
            raise PolicyCompileError(f"{path} requires values and does not accept value")
        expected = tuple(_sequence(raw["values"], f"{path}.values"))
    else:
        if "values" in raw or "value" not in raw:
            raise PolicyCompileError(f"{path} requires value and does not accept values")
        expected = copy.deepcopy(raw["value"])
    if operator in {"has_label", "derived_from"} and not isinstance(expected, str):
        raise PolicyCompileError(f"{path}.value must be a string for {operator}")
    if operator in {"lte", "gte"} and (
        not isinstance(expected, (int, float)) or isinstance(expected, bool)
    ):
        raise PolicyCompileError(f"{path}.value must be numeric for {operator}")
    return Condition(field=field, operator=operator, expected=expected)


def _parse_rules(value: Any) -> tuple[Rule, ...]:
    raw_rules = _sequence(value, "rules")
    if not raw_rules:
        raise PolicyCompileError("rules must not be empty")
    rules: list[Rule] = []
    seen: set[str] = set()
    for index, candidate in enumerate(raw_rules):
        path = f"rules[{index}]"
        raw = _mapping(candidate, path)
        _fields(
            raw,
            allowed={"id", "stage", "priority", "when", "effect", "reason"},
            required={"id", "stage", "when", "effect", "reason"},
            path=path,
        )
        rule_id = _text(raw["id"], f"{path}.id")
        if rule_id in seen:
            raise PolicyCompileError(f"duplicate rule id: {rule_id}")
        seen.add(rule_id)
        stage = _text(raw["stage"], f"{path}.stage")
        if stage != "before_tool":
            raise PolicyCompileError(f"{path}.stage is unsupported: {stage}")
        priority = raw.get("priority", 100)
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise PolicyCompileError(f"{path}.priority must be an integer")
        when = _mapping(raw["when"], f"{path}.when")
        _fields(
            when,
            allowed={"all"},
            required={"all"},
            path=f"{path}.when",
        )
        conditions = tuple(
            _parse_condition(item, f"{path}.when.all[{condition_index}]")
            for condition_index, item in enumerate(_sequence(when["all"], f"{path}.when.all"))
        )
        if not conditions:
            raise PolicyCompileError(f"{path}.when.all must not be empty")
        effect_text = _text(raw["effect"], f"{path}.effect")
        try:
            effect = Outcome(effect_text)
        except ValueError as error:
            raise PolicyCompileError(f"{path}.effect is unsupported: {effect_text}") from error
        if effect is Outcome.ERROR:
            raise PolicyCompileError(f"{path}.effect cannot be error")
        rules.append(
            Rule(
                id=rule_id,
                stage=stage,
                priority=priority,
                conditions=conditions,
                effect=effect,
                reason=_text(raw["reason"], f"{path}.reason"),
            )
        )
    return tuple(sorted(rules, key=lambda rule: (rule.priority, rule.id)))


def _parse_limits(value: Any, tools: dict[str, ToolDefinition]) -> tuple[Limit, ...]:
    raw_limits = _sequence(value, "limits")
    limits: list[Limit] = []
    seen: set[str] = set()
    for index, candidate in enumerate(raw_limits):
        path = f"limits[{index}]"
        raw = _mapping(candidate, path)
        _fields(
            raw,
            allowed={"id", "tool", "kind", "max", "argument"},
            required={"id", "tool", "kind", "max"},
            path=path,
        )
        limit_id = _text(raw["id"], f"{path}.id")
        if limit_id in seen:
            raise PolicyCompileError(f"duplicate limit id: {limit_id}")
        seen.add(limit_id)
        tool = _text(raw["tool"], f"{path}.tool")
        if tool not in tools:
            raise PolicyCompileError(f"{path}.tool is not declared: {tool}")
        kind = _text(raw["kind"], f"{path}.kind")
        if kind not in {"count", "sum"}:
            raise PolicyCompileError(f"{path}.kind must be count or sum")
        maximum = raw["max"]
        if not isinstance(maximum, (int, float)) or isinstance(maximum, bool) or maximum < 0:
            raise PolicyCompileError(f"{path}.max must be a non-negative number")
        argument = raw.get("argument")
        if kind == "sum":
            argument = _text(argument, f"{path}.argument")
        elif argument is not None:
            raise PolicyCompileError(f"{path}.argument is only valid for sum limits")
        limits.append(
            Limit(
                id=limit_id,
                tool=tool,
                kind=kind,
                maximum=float(maximum),
                argument=argument,
            )
        )
    return tuple(limits)


def compile_policy(value: Any) -> CompiledPolicy:
    raw = _mapping(value, "policy")
    _fields(
        raw,
        allowed={"apiVersion", "kind", "defaults", "tools", "rules", "limits"},
        required={"apiVersion", "kind", "defaults", "tools", "rules"},
        path="policy",
    )
    if raw["apiVersion"] != API_VERSION:
        raise PolicyCompileError(f"apiVersion must be {API_VERSION}")
    if raw["kind"] != KIND:
        raise PolicyCompileError(f"kind must be {KIND}")
    defaults = _mapping(raw["defaults"], "defaults")
    _fields(
        defaults,
        allowed={"unmatched"},
        required={"unmatched"},
        path="defaults",
    )
    if defaults["unmatched"] != "deny":
        raise PolicyCompileError("defaults.unmatched must be deny")
    tools = _parse_tools(raw["tools"])
    rules = _parse_rules(raw["rules"])
    limits = _parse_limits(raw.get("limits", []), tools)
    source = copy.deepcopy(raw)
    try:
        policy_hash = digest_json(source)
    except CanonicalizationError as error:
        raise PolicyCompileError(f"policy is not canonical JSON data: {error}") from error
    return CompiledPolicy(
        policy_hash=policy_hash,
        tools=tools,
        rules=rules,
        limits=limits,
        source=source,
    )


def load_policy(path: str | Path) -> CompiledPolicy:
    try:
        raw = Path(path).read_bytes()
        if len(raw) > MAX_POLICY_BYTES:
            raise PolicyCompileError(f"policy exceeds {MAX_POLICY_BYTES} bytes")
        # _UniqueKeyLoader subclasses SafeLoader and only adds duplicate-key rejection.
        value = yaml.load(raw.decode("utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506
    except PolicyCompileError:
        raise
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise PolicyCompileError(f"could not load policy: {error}") from error
    return compile_policy(value)
