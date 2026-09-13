from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from railproof.canonical import canonical_json
from railproof.exceptions import ApprovalInvalid
from railproof.models import ApprovalChallenge, ApprovalRecord, Principal

MIN_SIGNING_KEY_BYTES = 32
MAX_APPROVAL_TOKEN_BYTES = 8_192


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class ApprovalBroker:
    def __init__(
        self,
        signing_key: bytes,
        *,
        clock: Callable[[], datetime] = _now,
        ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if len(signing_key) < MIN_SIGNING_KEY_BYTES:
            raise ValueError("approval signing key must contain at least 32 bytes")
        if ttl <= timedelta(0):
            raise ValueError("approval ttl must be positive")
        self._signing_key = bytes(signing_key)
        self._clock = clock
        self._ttl = ttl
        self._used_nonces: set[str] = set()
        self._lock = threading.Lock()

    def challenge(
        self, *, action_hash: str, policy_hash: str, principal: Principal
    ) -> ApprovalChallenge:
        return ApprovalChallenge(
            nonce=secrets.token_urlsafe(24),
            action_hash=action_hash,
            policy_hash=policy_hash,
            principal=principal,
            expires_at=self._clock() + self._ttl,
        )

    def approve(self, challenge: ApprovalChallenge, *, approver_id: str) -> str:
        if not approver_id:
            raise ValueError("approver_id must not be empty")
        if challenge.expires_at.tzinfo is None:
            raise ApprovalInvalid("approval expiry must be timezone-aware")
        if self._clock() >= challenge.expires_at:
            raise ApprovalInvalid("approval challenge has expired")
        payload = {
            "action_hash": challenge.action_hash,
            "approver_id": approver_id,
            "expires_at": challenge.expires_at.astimezone(UTC).isoformat(),
            "nonce": challenge.nonce,
            "policy_hash": challenge.policy_hash,
            "principal": {
                "id": challenge.principal.id,
                "roles": challenge.principal.roles,
                "tenant": challenge.principal.tenant,
            },
        }
        encoded = _encode(canonical_json(payload).encode())
        signature = _encode(hmac.digest(self._signing_key, encoded.encode(), hashlib.sha256))
        return f"{encoded}.{signature}"

    def verify(
        self,
        token: str,
        *,
        action_hash: str,
        policy_hash: str,
        principal: Principal,
    ) -> ApprovalRecord:
        payload = self._verified_payload(token)
        if payload.get("action_hash") != action_hash:
            raise ApprovalInvalid("approval is bound to a different action")
        if payload.get("policy_hash") != policy_hash:
            raise ApprovalInvalid("approval is bound to a different policy")
        expected_principal = {
            "id": principal.id,
            "roles": list(principal.roles),
            "tenant": principal.tenant,
        }
        if payload.get("principal") != expected_principal:
            raise ApprovalInvalid("approval is bound to a different principal")
        try:
            expires_at = datetime.fromisoformat(str(payload["expires_at"]))
            nonce = str(payload["nonce"])
            approver_id = str(payload["approver_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ApprovalInvalid("approval payload is malformed") from error
        if expires_at.tzinfo is None:
            raise ApprovalInvalid("approval expiry must be timezone-aware")
        if self._clock() >= expires_at:
            raise ApprovalInvalid("approval has expired")
        with self._lock:
            if nonce in self._used_nonces:
                raise ApprovalInvalid("approval has already been used")
            self._used_nonces.add(nonce)
        return ApprovalRecord(nonce=nonce, approver_id=approver_id, expires_at=expires_at)

    def _verified_payload(self, token: str) -> dict[str, Any]:
        if (
            not isinstance(token, str)
            or not token
            or len(token.encode()) > MAX_APPROVAL_TOKEN_BYTES
        ):
            raise ApprovalInvalid("approval token is malformed")
        try:
            encoded, supplied_signature = token.split(".", maxsplit=1)
            expected_signature = _encode(
                hmac.digest(self._signing_key, encoded.encode(), hashlib.sha256)
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ApprovalInvalid("approval signature is invalid")
            payload = json.loads(_decode(encoded))
        except ApprovalInvalid:
            raise
        except (binascii.Error, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ApprovalInvalid("approval token is malformed") from error
        if not isinstance(payload, dict):
            raise ApprovalInvalid("approval payload is malformed")
        return payload
