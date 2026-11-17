"""Domain types for one uptime check.

The core shape is the stage ladder. A check climbs DNS, TCP, TLS and HTTP in
that order on one connection. An observation records the duration of each
stage it completed, then ends in one of two ways. It gets an HTTP answer, or
it stops at the first stage that failed. A status code without a TCP connect,
or a TLS time after a TCP failure, cannot be constructed.

Later check kinds (TCP on other ports, SSL expiry, DNS) stop at a lower rung
of the same ladder. They reuse this shape and add their own end facts.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Literal, NewType, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountId = NewType("AccountId", int)
TargetId = NewType("TargetId", int)
CheckId = NewType("CheckId", int)
ProbeId = NewType("ProbeId", int)

Hostname = NewType("Hostname", str)
"""Lowercase IDNA (punycode) name. No scheme, port, path, or IP literal."""

UrlPath = NewType("UrlPath", str)
"""Absolute request path, starts with "/", at most 2048 bytes, ASCII only."""

SlotStart = NewType("SlotStart", datetime)
"""UTC instant aligned to a multiple of the check interval since the epoch.

Only scheduler.slot_start() makes one. It is the time part of a result key.
"""


def parse_hostname(raw: str) -> Hostname:
    """Parse owner input into a Hostname. This is the only constructor.

    Accepts "Example.COM", "bücher.example", and "https://example.com/x"
    (the host part only). Rejects IP literals, because IP mode is a separate
    product mode. Accepts "localhost" so tests can target a local server.
    """
    raise NotImplementedError


def parse_path(raw: str) -> UrlPath:
    raise NotImplementedError


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CheckKind(StrEnum):
    HTTPS = "https"


class CheckSpec(Frozen):
    """Everything the worker needs to run one check. The store builds it."""

    check_id: CheckId
    account_id: AccountId
    kind: CheckKind
    host: Hostname
    port: Annotated[int, Field(ge=1, le=65535)]
    path: UrlPath
    interval_s: int


class Stage(StrEnum):
    """Rungs of the ladder, in climb order. Enum order is the ladder order."""

    DNS = "dns"
    TCP = "tcp"
    TLS = "tls"
    HTTP = "http"


class FailureReason(StrEnum):
    """Why a stage stopped. verdict.judge() maps each one to a verdict."""

    NXDOMAIN = "nxdomain"
    DNS_TEMPORARY = "dns_temporary"
    DNS_NO_ADDRESS = "dns_no_address"
    TIMEOUT = "timeout"
    REFUSED = "refused"
    HOST_UNREACHABLE = "host_unreachable"
    NO_ROUTE = "no_route"
    RESET = "reset"
    TLS_CERT_INVALID = "tls_cert_invalid"
    TLS_HANDSHAKE = "tls_handshake"
    BAD_RESPONSE = "bad_response"
    CLOSED = "closed"
    LOCAL_RESOURCE = "local_resource"
    PROBE_INTERNAL = "probe_internal"


class StageTimings(Frozen):
    """Milliseconds for each completed stage.

    Invariant: the set fields are a prefix of the ladder. http_ms is the time
    from the request write to the end of the response headers.
    """

    dns_ms: int | None = None
    tcp_ms: int | None = None
    tls_ms: int | None = None
    http_ms: int | None = None

    def completed(self) -> tuple[Stage, ...]:
        raise NotImplementedError

    @model_validator(mode="after")
    def _prefix_of_ladder(self) -> Self:
        # TODO: walk Stage in order; once one field is None, all later fields must be None.
        raise NotImplementedError


class CloudflarePage(StrEnum):
    """Which Cloudflare interstitial the body prefix matched, if any."""

    CHALLENGE = "challenge"
    BLOCK = "block"


class Answer(Frozen):
    """The target sent a parseable HTTP status line and headers.

    Holds only the facts the verdict rules read. The probe extracts them at
    the boundary, so no raw header map or body leaves probe.py.
    """

    kind: Literal["answer"] = "answer"
    status: Annotated[int, Field(ge=100, le=599)]
    server: str | None
    cf_mitigated: str | None
    cf_page: CloudflarePage | None


class Failure(Frozen):
    """The climb stopped at `stage` for `reason`."""

    kind: Literal["failure"] = "failure"
    stage: Stage
    reason: FailureReason
    detail: Annotated[str, Field(max_length=200)]
    """errno name, ssl verify message, or exception class. For humans only."""


class Observation(Frozen):
    """What one probe saw for one check at one time. Facts only, no verdict.

    Invariants (validated once, trusted downstream):
    - end is Answer      -> timings completed all four stages.
    - end is Failure(s)  -> timings completed exactly the stages before s.
    - remote_addr is set -> DNS completed.
    """

    started_at: datetime
    remote_addr: IPv4Address | IPv6Address | None
    timings: StageTimings
    total_ms: int
    end: Annotated[Answer | Failure, Field(discriminator="kind")]

    @model_validator(mode="after")
    def _end_matches_ladder(self) -> Self:
        raise NotImplementedError


class ResultKey(Frozen):
    """Identity of one result row. One row per check, slot, and probe.

    A second write with the same key is a no-op, so a rerun after a crash or
    a second worker by mistake cannot add or change a row.
    """

    check_id: CheckId
    slot_start: SlotStart
    probe_id: ProbeId
