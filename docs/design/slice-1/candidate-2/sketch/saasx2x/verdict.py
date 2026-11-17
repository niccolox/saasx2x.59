"""Verdict rules. Pure functions from an Observation to a Judgment.

This module is the only place that decides what an observation means. The
store calls judge() when it writes a row and stamps RULES_VERSION on it, so
a later rule change can recompute old rows from their stored facts.

Rules for an Answer, first match wins:

| # | Condition                                                       | Verdict | Block signal           |
|---|-----------------------------------------------------------------|---------|------------------------|
| 1 | cf-mitigated header is "challenge" (any status)                 | blocked | cf_mitigated_challenge |
| 2 | server is cloudflare, status 403/429/503, body is challenge page | blocked | cf_challenge_page      |
| 3 | server is cloudflare, status 403, body is block page (WAF 1020)  | blocked | cf_block_page          |
| 4 | status 429 (any server)                                         | blocked | rate_limited           |
| 5 | status 200-399, or 401                                          | up      |                        |
| 6 | any other status (other 4xx, all 5xx, Cloudflare 52x)           | down    |                        |

Redirects are not followed. A 3xx means the target's server answered.
401 is up because the server answered and asks for credentials, which is
normal for an owner's admin site. 429 is blocked, not down, because the
target protects itself from the probe and still serves users.

Rules for a Failure come from REASON_VERDICT below. A failure is
probe_error only when the evidence is local to the probe host (no route in
its own routing table, out of file descriptors, a bug in the probe).
Ambiguous failures (DNS SERVFAIL, timeouts, host unreachable) are down for
this probe. Agreement across probes and control targets in later slices
separates a target outage from a probe outage for those reasons.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from saasx2x.domain import Answer, Failure, FailureReason, Observation, Frozen

RULES_VERSION = 1
"""Bump when any rule in this module changes. Stored on every row."""


class Verdict(StrEnum):
    UP = "up"
    DOWN = "down"
    BLOCKED = "blocked"
    PROBE_ERROR = "probe_error"


class BlockSignal(StrEnum):
    CF_MITIGATED_CHALLENGE = "cf_mitigated_challenge"
    CF_CHALLENGE_PAGE = "cf_challenge_page"
    CF_BLOCK_PAGE = "cf_block_page"
    RATE_LIMITED = "rate_limited"


class Judgment(Frozen):
    verdict: Verdict
    block_signal: BlockSignal | None = None

    @model_validator(mode="after")
    def _blocked_iff_signal(self) -> Self:
        # TODO: verdict is BLOCKED exactly when block_signal is not None.
        raise NotImplementedError


REASON_VERDICT: dict[FailureReason, Verdict] = {
    FailureReason.NXDOMAIN: Verdict.DOWN,
    FailureReason.DNS_TEMPORARY: Verdict.DOWN,
    FailureReason.DNS_NO_ADDRESS: Verdict.DOWN,
    FailureReason.TIMEOUT: Verdict.DOWN,
    FailureReason.REFUSED: Verdict.DOWN,
    FailureReason.HOST_UNREACHABLE: Verdict.DOWN,
    FailureReason.NO_ROUTE: Verdict.PROBE_ERROR,
    FailureReason.RESET: Verdict.DOWN,
    FailureReason.TLS_CERT_INVALID: Verdict.DOWN,
    FailureReason.TLS_HANDSHAKE: Verdict.DOWN,
    FailureReason.BAD_RESPONSE: Verdict.DOWN,
    FailureReason.CLOSED: Verdict.DOWN,
    FailureReason.LOCAL_RESOURCE: Verdict.PROBE_ERROR,
    FailureReason.PROBE_INTERNAL: Verdict.PROBE_ERROR,
}
"""Total over FailureReason. An import-time assert fails if a member is missing."""
assert REASON_VERDICT.keys() == set(FailureReason), "REASON_VERDICT must cover every FailureReason"


def judge(observation: Observation) -> Judgment:
    """Map one observation to its verdict. Pure and total."""
    match observation.end:
        case Answer() as answer:
            return _judge_answer(answer)
        case Failure(reason=reason):
            return Judgment(verdict=REASON_VERDICT[reason])


def _judge_answer(answer: Answer) -> Judgment:
    # TODO: apply rules 1-6 from the module docstring, in order.
    raise NotImplementedError
