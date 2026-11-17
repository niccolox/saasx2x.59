"""The verdict rules. Pure. This module is the only place that knows what "up" means."""

from collections import Counter
from collections.abc import Sequence
from enum import StrEnum
from typing import Final, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, computed_field

from saasx2x.domain import (
    AccountId,
    CheckId,
    DnsFailed,
    HttpFailed,
    HttpResponded,
    HttpsObservation,
    Milliseconds,
    ProbeFailed,
    ProbeId,
    TcpFailed,
    TlsFailed,
)


class Verdict(StrEnum):
    UP = "up"
    DOWN = "down"
    BLOCKED = "blocked"
    """Cloudflare or a rate limit refused the probe. Not a down state. Sends no down alert."""
    INCONCLUSIVE = "inconclusive"
    """The check gave no evidence about the target. Not a down state."""


class Reason(StrEnum):
    """The rule that gave the verdict. Each member owns its verdict, so the two cannot disagree."""

    verdict: Verdict

    def __new__(cls, value: str, verdict: Verdict) -> Self:
        member = str.__new__(cls, value)
        member._value_ = value
        member.verdict = verdict
        return member

    CLOUDFLARE_CHALLENGE = "cloudflare_challenge", Verdict.BLOCKED
    CLOUDFLARE_BLOCK_PAGE = "cloudflare_block_page", Verdict.BLOCKED
    RATE_LIMITED = "rate_limited", Verdict.BLOCKED
    STATUS_OK = "status_ok", Verdict.UP
    LOGIN_REQUIRED = "login_required", Verdict.UP
    ERROR_STATUS = "error_status", Verdict.DOWN
    DNS_NOT_FOUND = "dns_not_found", Verdict.DOWN
    TCP_FAILED = "tcp_failed", Verdict.DOWN
    TLS_FAILED = "tls_failed", Verdict.DOWN
    HTTP_FAILED = "http_failed", Verdict.DOWN
    DNS_UNAVAILABLE = "dns_unavailable", Verdict.INCONCLUSIVE
    PROBE_FAILED = "probe_failed", Verdict.INCONCLUSIVE


VERDICT_TIE_ORDER: Final = (Verdict.UP, Verdict.BLOCKED, Verdict.INCONCLUSIVE, Verdict.DOWN)
"""On a tie between verdicts, the first verdict in this order wins.
PRODUCT.md: one failed probe is not an outage."""


def fold_probes(reasons: Sequence[Reason]) -> Reason:
    """Fold the rows that the probes wrote for one slot into one judgement. Pure.

    `reasons` has one item for each probe row of the slot, in any order, and at least one item.
    The result is always one of the items, so a judgement keeps a real reason.

    1. Count the rows for each verdict. The verdict with the most rows wins.
    2. On a tie, the first verdict in `VERDICT_TIE_ORDER` wins.
    3. Of the reasons with that verdict, the most frequent wins. On a tie, the first in the
       order of `Reason` wins.

    `RULES_VERSION` does not change for this rule: no stored value depends on it.
    """
    rows = Counter(reasons)
    verdicts = Counter(reason.verdict for reason in reasons)
    verdict = max(VERDICT_TIE_ORDER, key=verdicts.__getitem__)
    return max((r for r in Reason if r.verdict is verdict and r in rows), key=rows.__getitem__)


RULES_VERSION: Final = 1
"""Increase this number with each change to the rules below. Each result row records it."""

OK_STATUSES: Final = range(200, 400)
LOGIN_REQUIRED_STATUS: Final = 401
RATE_LIMITED_STATUS: Final = 429
CLOUDFLARE_BLOCK_STATUSES: Final = frozenset({403, 429, 503})
CLOUDFLARE_BLOCK_MARKERS: Final = (
    "<title>just a moment...</title>",
    "/cdn-cgi/challenge-platform/",
    "<title>attention required! | cloudflare</title>",
    "error code: 10",
)


def decide_verdict(observation: HttpsObservation) -> Reason:
    """Map one observation to the rule that judges it. Total and pure."""
    match observation:
        case HttpResponded():
            return _judge_response(observation)
        case DnsFailed():
            match observation.error:
                case "not_found":
                    return Reason.DNS_NOT_FOUND
                case "unavailable":
                    return Reason.DNS_UNAVAILABLE
        case TcpFailed():
            return Reason.TCP_FAILED
        case TlsFailed():
            return Reason.TLS_FAILED
        case HttpFailed():
            return Reason.HTTP_FAILED
        case ProbeFailed():
            return Reason.PROBE_FAILED


def _judge_response(response: HttpResponded) -> Reason:
    if (response.cf_mitigated or "").lower() == "challenge":
        return Reason.CLOUDFLARE_CHALLENGE
    if _is_cloudflare_block_page(response):
        return Reason.CLOUDFLARE_BLOCK_PAGE
    if response.status == RATE_LIMITED_STATUS:
        return Reason.RATE_LIMITED
    if response.status in OK_STATUSES:
        return Reason.STATUS_OK
    if response.status == LOGIN_REQUIRED_STATUS:
        return Reason.LOGIN_REQUIRED
    return Reason.ERROR_STATUS


def _is_cloudflare_block_page(response: HttpResponded) -> bool:
    # `server: cloudflare` alone is not enough: Cloudflare sets it on each response that it
    # proxies, so an origin 503 has it too, and an origin 503 is "down".
    if (response.server or "").lower() != "cloudflare":
        return False
    if response.status not in CLOUDFLARE_BLOCK_STATUSES or response.body_head is None:
        return False
    body = response.body_head.lower()
    return any(marker in body for marker in CLOUDFLARE_BLOCK_MARKERS)


class CheckResult(BaseModel):
    """One row of `check_results`. The reason and the verdict derive from the observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: CheckId
    account_id: AccountId
    probe_id: ProbeId
    scheduled_at: AwareDatetime
    """The slot start. With `check_id` and `probe_id`, the identity of the row."""
    due_at: AwareDatetime
    started_at: AwareDatetime
    duration_ms: Milliseconds
    observation: HttpsObservation

    @computed_field
    @property
    def reason(self) -> Reason:
        return decide_verdict(self.observation)

    @computed_field
    @property
    def verdict(self) -> Verdict:
        return self.reason.verdict

    @computed_field
    @property
    def rules_version(self) -> int:
        return RULES_VERSION
