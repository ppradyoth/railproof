from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


class Outcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Principal:
    id: str
    tenant: str | None = None
    roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Action:
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    session_id: str
    stage: str
    principal: Principal
    action: Action
    labels: dict[str, frozenset[str]] = field(default_factory=dict)
    provenance: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    call_counts: dict[str, int] = field(default_factory=dict)
    sums: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Decision:
    decision_id: str
    outcome: Outcome
    policy_hash: str
    action_hash: str
    matched_rules: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ApprovalChallenge:
    nonce: str
    action_hash: str
    policy_hash: str
    principal: Principal
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    nonce: str
    approver_id: str
    expires_at: datetime
