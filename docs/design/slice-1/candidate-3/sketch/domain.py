"""Pure domain types. No I/O, no imports from other saasx2x modules.

Every type here is frozen. Observation is a tagged union, so a state such as
"HTTP status present but TCP failed" cannot be built.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, NewType
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


CheckId = NewType("CheckId", UUID)
TargetId = NewType("TargetId", UUID)
AccountId = NewType("AccountId", UUID)
ProbeId = NewType("ProbeId", str)  # slug, same pattern as the probe.id CHECK in schema.sql


class CheckKind(StrEnum):
    HTTPS_443 = "https_443"  # slice 1 has this kind only


def parse_hostname(raw: str) -> str:
    """Boundary parser. Lowercase ASCII (IDNA) DNS name. Reject IP literals, scheme, port, path.
    Raise ValueError with a message the CLI prints as is."""
    raise NotImplementedError


Hostname = Annotated[str, AfterValidator(parse_hostname)]
"""A str that passed parse_hostname. Pydantic re-checks it on every model build,
so a Hostname inside a model is always normalized."""


class Slot(Frozen):
    """One cell of the fixed-rate grid: [start, start + interval_s).

    The grid is wall-clock UTC, anchored at the epoch. Every probe in every region
    computes the same start for the same instant. The slot is the idempotency key
    and the agreement key.
    """

    start: AwareDatetime
    interval_s: Annotated[int, Field(ge=60, multiple_of=60)]

    @classmethod
    def containing(cls, now: datetime, interval_s: int) -> Slot:
        """start = floor(epoch(now) / interval_s) * interval_s."""
        raise NotImplementedError

    @property
    def end(self) -> datetime:
        raise NotImplementedError

    def is_current(self, now: datetime) -> bool:
        """True while now is inside the slot. Queued work for a past slot is dropped."""
        raise NotImplementedError


# ---- Observation: raw facts from one probe attempt -------------------------------------

Vantage = Literal["reachable", "unreachable"]
"""Result of the probe's own network test. Run only when no HTTP response arrived.
'unreachable' means every anchor failed, so the probe network is the likely cause."""


class TcpErrorKind(StrEnum):
    DNS = "dns"
    REFUSED = "refused"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"  # any other OSError on connect


class HttpErrorKind(StrEnum):
    TLS = "tls"  # certificate or handshake failure
    TIMEOUT = "timeout"
    RESET = "reset"
    PROTOCOL = "protocol"


class TcpOk(Frozen):
    connect_ms: int = Field(ge=0)


class TcpErr(Frozen):
    kind: TcpErrorKind
    elapsed_ms: int = Field(ge=0)


class HttpResponse(Frozen):
    status: int = Field(ge=100, le=599)
    total_ms: int = Field(ge=0)
    server: str | None  # raw Server header, lowercased
    cf_mitigated: str | None  # raw cf-mitigated header, lowercased
    body_head: str | None  # first 2 KiB, kept only when status >= 400. Evidence for rule replay.


class HttpErr(Frozen):
    kind: HttpErrorKind
    elapsed_ms: int = Field(ge=0)


class ConnectFailed(Frozen):
    phase: Literal["tcp_failed"] = "tcp_failed"
    tcp: TcpErr
    vantage: Vantage


class NoResponse(Frozen):
    phase: Literal["http_failed"] = "http_failed"
    tcp: TcpOk
    http: HttpErr
    vantage: Vantage


class Responded(Frozen):
    phase: Literal["http_responded"] = "http_responded"
    tcp: TcpOk
    http: HttpResponse


Observation = Annotated[ConnectFailed | NoResponse | Responded, Field(discriminator="phase")]
"""The stored form of one https_443 attempt. The jsonb column holds this model.
Later check kinds add their own union. check_result.observation is parsed by check kind."""


# ---- Work items ------------------------------------------------------------------------

class DueCheck(Frozen):
    """A check with no stored result for its current slot, for this probe."""

    check_id: CheckId
    host: Hostname
    kind: CheckKind
    slot: Slot


class Target(Frozen):
    id: TargetId
    account_id: AccountId
    host: Hostname
    interval: timedelta
    added_at: AwareDatetime
