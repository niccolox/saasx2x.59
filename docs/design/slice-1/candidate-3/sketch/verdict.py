"""The only place that maps raw observations to verdicts. Pure functions, no I/O.

Rule changes bump RULES_VERSION. Stored rows keep the full Observation, so a later
tool can re-judge old rows with new rules.
"""
from __future__ import annotations

from enum import Enum, StrEnum
from typing import Final

from pydantic import AwareDatetime, computed_field

from domain import CheckId, Frozen, Observation, ProbeId, Slot

RULES_VERSION: Final = 1


class Verdict(StrEnum):
    UP = "up"
    DOWN = "down"
    BLOCKED = "blocked"  # Cloudflare challenge. Never sends a down alert.
    PROBE_FAULT = "probe_fault"  # probe network failed. Says nothing about the target.


class Reason(Enum):
    """One member per stored reason. The member owns its verdict, so no pair can disagree.

    schema.sql lists the same pairs in a CHECK. test_schema_matches_enums fails if the lists differ.
    """

    verdict: Verdict

    OK = ("ok", Verdict.UP)
    STATUS_4XX = ("status_4xx", Verdict.DOWN)
    STATUS_5XX = ("status_5xx", Verdict.DOWN)
    DNS_FAILURE = ("dns_failure", Verdict.DOWN)
    TCP_REFUSED = ("tcp_refused", Verdict.DOWN)
    TCP_TIMEOUT = ("tcp_timeout", Verdict.DOWN)
    TCP_UNREACHABLE = ("tcp_unreachable", Verdict.DOWN)
    TLS_FAILURE = ("tls_failure", Verdict.DOWN)
    HTTP_TIMEOUT = ("http_timeout", Verdict.DOWN)
    CONNECTION_RESET = ("connection_reset", Verdict.DOWN)
    HTTP_PROTOCOL_ERROR = ("http_protocol_error", Verdict.DOWN)
    CLOUDFLARE_CHALLENGE = ("cloudflare_challenge", Verdict.BLOCKED)
    PROBE_NETWORK_DOWN = ("probe_network_down", Verdict.PROBE_FAULT)

    def __new__(cls, value: str, verdict: Verdict) -> Reason:
        member = object.__new__(cls)
        member._value_ = value
        member.verdict = verdict
        return member


CF_CHALLENGE_MARKERS: Final = (
    "just a moment...",
    "/cdn-cgi/challenge-platform/",
    "cf-chl-",
    "attention required! | cloudflare",
)


def judge(obs: Observation) -> Reason:
    """Rules, first match wins.

    1. Responded and is_cloudflare_block(): CLOUDFLARE_CHALLENGE.
    2. Responded, status 200..399: OK. The probe does not follow redirects.
    3. Responded, status 400..499: STATUS_4XX. Responded, 500..599: STATUS_5XX.
    4. ConnectFailed or NoResponse with vantage == "unreachable": PROBE_NETWORK_DOWN.
    5. ConnectFailed or NoResponse: map the error kind to its Reason with an exhaustive match.
    """
    raise NotImplementedError


def is_cloudflare_block(status: int, server: str | None, cf_mitigated: str | None,
                        body_head: str | None) -> bool:
    """True when cf_mitigated == "challenge" (any status), or when server starts with
    "cloudflare", status is 403 or 503, and body_head holds a CF_CHALLENGE_MARKERS entry.
    A bare Cloudflare 503 without a marker is DOWN, because an origin outage looks the same."""
    raise NotImplementedError


class CheckResult(Frozen):
    """What the store writes. The verdict is derived from the observation, never passed in."""

    check_id: CheckId
    probe_id: ProbeId
    slot: Slot
    started_at: AwareDatetime
    finished_at: AwareDatetime
    observation: Observation

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reason(self) -> Reason:
        return judge(self.observation)

    @property
    def verdict(self) -> Verdict:
        return self.reason.verdict
