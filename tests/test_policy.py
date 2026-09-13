import copy
from pathlib import Path

import pytest

from railproof.exceptions import PolicyCompileError
from railproof.policy import compile_policy, load_policy


def test_loads_policy_and_produces_stable_hash(policy_path: Path) -> None:
    first = load_policy(policy_path)
    second = load_policy(policy_path)

    assert first.policy_hash == second.policy_hash
    assert set(first.tools) == {"get_weather", "send_email"}
    assert [rule.id for rule in first.rules] == [
        "block-sensitive-external",
        "block-untrusted-recipient",
        "approve-email",
        "allow-weather",
    ]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"unknown": True}, "unknown field"),
        ({"apiVersion": "wrong"}, "apiVersion"),
        ({"kind": "Wrong"}, "kind"),
        ({"rules": []}, "rules"),
    ],
)
def test_rejects_invalid_top_level_policy(mutation, message) -> None:
    raw = {
        "apiVersion": "railproof.dev/v1alpha1",
        "kind": "AgentSecurityPolicy",
        "defaults": {"unmatched": "deny"},
        "tools": {
            "tool": {
                "risk": "low",
                "sink": "internal",
                "schema": {"type": "object"},
            }
        },
        "rules": [
            {
                "id": "allow-tool",
                "stage": "before_tool",
                "when": {"all": [{"field": "action.tool", "op": "eq", "value": "tool"}]},
                "effect": "allow",
                "reason": "allowed",
            }
        ],
    }
    raw.update(mutation)

    with pytest.raises(PolicyCompileError, match=message):
        compile_policy(raw)


def test_rejects_duplicate_rule_ids(policy_path: Path) -> None:
    policy = load_policy(policy_path)
    raw = dict(policy.source)
    raw["rules"] = [*raw["rules"], raw["rules"][0]]

    with pytest.raises(PolicyCompileError, match="duplicate rule id"):
        compile_policy(raw)


def test_rejects_unsafe_default(policy_path: Path) -> None:
    policy = load_policy(policy_path)
    raw = dict(policy.source)
    raw["defaults"] = {"unmatched": "allow"}

    with pytest.raises(PolicyCompileError, match="unmatched must be deny"):
        compile_policy(raw)


def test_rejects_unknown_condition_operator(policy_path: Path) -> None:
    policy = load_policy(policy_path)
    raw = dict(policy.source)
    raw["rules"][0]["when"]["all"][0]["op"] = "python_eval"

    with pytest.raises(PolicyCompileError, match="unsupported operator"):
        compile_policy(raw)


def test_rejects_invalid_tool_schema(policy_path: Path) -> None:
    policy = load_policy(policy_path)
    raw = dict(policy.source)
    raw["tools"]["get_weather"]["schema"] = {"type": "not-a-json-schema-type"}

    with pytest.raises(PolicyCompileError, match="invalid JSON Schema"):
        compile_policy(raw)


def test_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text("apiVersion: one\napiVersion: two\n", encoding="utf-8")
    with pytest.raises(PolicyCompileError, match="duplicate YAML key"):
        load_policy(path)


def test_safe_loader_rejects_python_object_tags(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.yaml"
    path.write_text("!!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8")
    with pytest.raises(PolicyCompileError, match="could not load policy"):
        load_policy(path)


@pytest.mark.parametrize("reference", ["https://example.com/schema.json", "#/$defs/value"])
def test_rejects_schema_reference(policy_path: Path, reference: str) -> None:
    raw = copy.deepcopy(load_policy(policy_path).source)
    raw["tools"]["get_weather"]["schema"] = {"$ref": reference}
    with pytest.raises(PolicyCompileError, match=r"unsupported \$ref"):
        compile_policy(raw)


def test_rejects_oversized_policy(tmp_path: Path) -> None:
    path = tmp_path / "oversized.yaml"
    path.write_bytes(b"x" * 1_048_577)
    with pytest.raises(PolicyCompileError, match="exceeds"):
        load_policy(path)


def test_rejects_excessive_yaml_aliases(tmp_path: Path) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text(
        "items:\n  - &item value\n" + "".join("  - *item\n" for _ in range(101)),
        encoding="utf-8",
    )
    with pytest.raises(PolicyCompileError, match="alias count"):
        load_policy(path)


@pytest.mark.parametrize(
    "field",
    ["session.unknown", "session.call_count.", "session.sum.", "action.arguments."],
)
def test_rejects_unsupported_or_incomplete_dynamic_field(policy_path: Path, field: str) -> None:
    raw = copy.deepcopy(load_policy(policy_path).source)
    raw["rules"][0]["when"]["all"][0]["field"] = field
    with pytest.raises(PolicyCompileError, match=r"unsupported|incomplete"):
        compile_policy(raw)


def test_rejects_empty_or_padded_tool_name(policy_path: Path) -> None:
    raw = copy.deepcopy(load_policy(policy_path).source)
    raw["tools"][" padded "] = raw["tools"].pop("get_weather")
    with pytest.raises(PolicyCompileError, match="tool name"):
        compile_policy(raw)
