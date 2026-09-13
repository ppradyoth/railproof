import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from railproof.approval import ApprovalBroker
from railproof.exceptions import ApprovalInvalid
from railproof.models import ApprovalChallenge, Principal


def challenge(*, action_hash: str = "action_a") -> ApprovalChallenge:
    return ApprovalChallenge(
        nonce="nonce_a",
        action_hash=action_hash,
        policy_hash="policy_a",
        principal=Principal(id="user_1", tenant="tenant_a"),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


def test_approval_is_bound_to_exact_action() -> None:
    broker = ApprovalBroker(b"a" * 32)
    token = broker.approve(challenge(), approver_id="reviewer_1")

    with pytest.raises(ApprovalInvalid, match="action"):
        broker.verify(
            token,
            action_hash="action_b",
            policy_hash="policy_a",
            principal=Principal(id="user_1", tenant="tenant_a"),
        )


def test_approval_is_single_use() -> None:
    broker = ApprovalBroker(b"a" * 32)
    token = broker.approve(challenge(), approver_id="reviewer_1")
    principal = Principal(id="user_1", tenant="tenant_a")

    approval = broker.verify(
        token, action_hash="action_a", policy_hash="policy_a", principal=principal
    )

    assert approval.approver_id == "reviewer_1"
    with pytest.raises(ApprovalInvalid, match="already been used"):
        broker.verify(token, action_hash="action_a", policy_hash="policy_a", principal=principal)


def test_expired_approval_is_rejected() -> None:
    now = datetime(2030, 1, 2, tzinfo=UTC)
    broker = ApprovalBroker(b"a" * 32, clock=lambda: now)
    expired = ApprovalChallenge(
        nonce="nonce_expired",
        action_hash="action_a",
        policy_hash="policy_a",
        principal=Principal(id="user_1", tenant="tenant_a"),
        expires_at=now - timedelta(seconds=1),
    )
    with pytest.raises(ApprovalInvalid, match="expired"):
        broker.approve(expired, approver_id="reviewer_1")


def _signed_token(payload: object, key: bytes = b"a" * 32) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).rstrip(b"=")
    signature = base64.urlsafe_b64encode(hmac.digest(key, encoded, hashlib.sha256)).rstrip(b"=")
    return f"{encoded.decode()}.{signature.decode()}"


def test_broker_rejects_invalid_configuration_and_approver() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        ApprovalBroker(b"short")
    with pytest.raises(ValueError, match="positive"):
        ApprovalBroker(b"a" * 32, ttl=timedelta(0))

    broker = ApprovalBroker(b"a" * 32)
    with pytest.raises(ValueError, match="approver_id"):
        broker.approve(challenge(), approver_id="")


def test_broker_rejects_naive_expiry() -> None:
    broker = ApprovalBroker(b"a" * 32)
    naive = ApprovalChallenge(
        nonce="nonce",
        action_hash="action_a",
        policy_hash="policy_a",
        principal=Principal(id="user_1"),
        expires_at=datetime(2030, 1, 1),  # noqa: DTZ001
    )
    with pytest.raises(ApprovalInvalid, match="timezone-aware"):
        broker.approve(naive, approver_id="reviewer")


@pytest.mark.parametrize(
    ("token", "message"),
    [
        ("missing-separator", "malformed"),
        ("%%%.$$$", "signature"),
        ("e30.invalid", "signature"),
    ],
)
def test_broker_rejects_malformed_or_forged_tokens(token: str, message: str) -> None:
    broker = ApprovalBroker(b"a" * 32)
    with pytest.raises(ApprovalInvalid, match=message):
        broker.verify(
            token,
            action_hash="action_a",
            policy_hash="policy_a",
            principal=Principal(id="user_1", tenant="tenant_a"),
        )


def test_broker_rejects_oversized_or_non_string_token() -> None:
    broker = ApprovalBroker(b"a" * 32)
    principal = Principal(id="user_1", tenant="tenant_a")
    for token in ("x" * 8_193, b"not-a-string"):
        with pytest.raises(ApprovalInvalid, match="malformed"):
            broker.verify(
                cast("str", token),
                action_hash="action_a",
                policy_hash="policy_a",
                principal=principal,
            )


def test_broker_rejects_wrong_policy_and_principal() -> None:
    broker = ApprovalBroker(b"a" * 32)
    token = broker.approve(challenge(), approver_id="reviewer")
    with pytest.raises(ApprovalInvalid, match="policy"):
        broker.verify(
            token,
            action_hash="action_a",
            policy_hash="policy_b",
            principal=Principal(id="user_1", tenant="tenant_a"),
        )
    with pytest.raises(ApprovalInvalid, match="principal"):
        broker.verify(
            token,
            action_hash="action_a",
            policy_hash="policy_a",
            principal=Principal(id="user_2", tenant="tenant_a"),
        )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {
            "action_hash": "action_a",
            "policy_hash": "policy_a",
            "principal": {"id": "user_1", "roles": [], "tenant": "tenant_a"},
        },
        {
            "action_hash": "action_a",
            "policy_hash": "policy_a",
            "principal": {"id": "user_1", "roles": [], "tenant": "tenant_a"},
            "expires_at": "not-a-date",
            "nonce": "n",
            "approver_id": "r",
        },
        {
            "action_hash": "action_a",
            "policy_hash": "policy_a",
            "principal": {"id": "user_1", "roles": [], "tenant": "tenant_a"},
            "expires_at": "2030-01-01T00:00:00",
            "nonce": "n",
            "approver_id": "r",
        },
    ],
)
def test_broker_rejects_malformed_signed_payloads(payload: object) -> None:
    now = datetime(2029, 1, 1, tzinfo=UTC)
    broker = ApprovalBroker(b"a" * 32, clock=lambda: now)
    with pytest.raises(ApprovalInvalid, match=r"payload|expiry"):
        broker.verify(
            _signed_token(payload),
            action_hash="action_a",
            policy_hash="policy_a",
            principal=Principal(id="user_1", tenant="tenant_a"),
        )
