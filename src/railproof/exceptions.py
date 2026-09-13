from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from railproof.models import ApprovalChallenge, Decision


class RailproofError(Exception):
    pass


class PolicyCompileError(RailproofError):
    pass


class CanonicalizationError(RailproofError):
    pass


class AdapterError(RailproofError):
    pass


class ApprovalInvalid(RailproofError):
    pass


class PolicyDenied(RailproofError):
    def __init__(self, decision: Decision) -> None:
        self.decision = decision
        super().__init__(", ".join(decision.reason_codes))


class ApprovalRequired(RailproofError):
    def __init__(self, decision: Decision, challenge: ApprovalChallenge) -> None:
        self.decision = decision
        self.challenge = challenge
        super().__init__(", ".join(decision.reason_codes))


class ApprovalUnavailable(RailproofError):
    pass


class ExecutorNotRegistered(RailproofError):
    pass


class SessionCapacityExceeded(RailproofError):
    pass


class SessionBusy(RailproofError):
    pass
