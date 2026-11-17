"""Domain types for slice 1: what the probe checks and what the probe saw.

Pure. No I/O. `verdict.py` gives an observation its meaning.
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal, NewType
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, IPvAnyAddress, NonNegativeFloat

AccountSlug = NewType("AccountSlug", str)
TargetId = NewType("TargetId", UUID)
CheckId = NewType("CheckId", UUID)
ProbeId = NewType("ProbeId", UUID)
ProbeName = NewType("ProbeName", str)

Hostname = NewType("Hostname", str)
"""A lowercase ASCII FQDN. Only `parse_hostname` makes one."""

Milliseconds = NonNegativeFloat


def parse_hostname(raw: str) -> Hostname:
    """Parse owner input into a hostname. Raise ValueError for other input.

    Accept `Example.COM` and `example.com.`. Encode an international name with IDNA.
    Reject a scheme, a path, a port, and an IP literal. IP mode is a later slice.
    """
    raise NotImplementedError


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Slot(_Frozen):
    """One interval of the schedule. `start` is one part of the key of a result row.

    Invariant: `start` is UTC and `start.timestamp() % interval.total_seconds() == 0`.
    The wall clock gives the slot. No run gives the next slot, so the schedule cannot drift.
    """

    start: AwareDatetime
    interval: timedelta

    @property
    def end(self) -> datetime:
        raise NotImplementedError

    @classmethod
    def containing(cls, at: datetime, interval: timedelta) -> "Slot":
        """Return the slot that contains `at`. Pure."""
        raise NotImplementedError


class Target(_Frozen):
    """One site of one account, as `target list` shows it."""

    id: TargetId
    hostname: Hostname
    added_at: AwareDatetime


class DueCheck(_Frozen):
    """One check that has no result for a given probe and slot."""

    check_id: CheckId
    hostname: Hostname
    port: int = Field(ge=1, le=65535)


# The observation of one HTTPS check.
#
# A check has four stages on ONE connection: DNS, TCP, TLS, HTTP. The check stops at the first
# stage that fails. Each class below is one stop point and holds only the facts that exist at
# that point. A status code without a TCP connect time is not representable.


class DnsFailed(_Frozen):
    outcome: Literal["dns_failed"] = "dns_failed"
    error: Literal["not_found", "unavailable"]
    """not_found: the resolver answered that the name does not exist.
    unavailable: the resolver gave no answer. The cause can be the probe or the target."""


class _Resolved(_Frozen):
    ip: IPvAnyAddress
    """The address that the probe used. For a failure, the last address that the probe tried."""
    dns_ms: Milliseconds


class TcpFailed(_Resolved):
    outcome: Literal["tcp_failed"] = "tcp_failed"
    error: Literal["refused", "timeout", "unreachable", "reset"]


class _Connected(_Resolved):
    tcp_connect_ms: Milliseconds


class TlsFailed(_Connected):
    outcome: Literal["tls_failed"] = "tls_failed"
    error: Literal["certificate_invalid", "handshake_failed", "timeout"]
    detail: str
    """The verify message of the TLS library, for example "certificate has expired"."""


class _Secured(_Connected):
    tls_handshake_ms: Milliseconds


class HttpFailed(_Secured):
    outcome: Literal["http_failed"] = "http_failed"
    error: Literal["timeout", "connection_closed", "protocol_error"]


class HttpResponded(_Secured):
    outcome: Literal["http_responded"] = "http_responded"
    http_ms: Milliseconds
    """Time from the first request byte to the last response header byte."""
    status: int = Field(ge=200, le=599)
    server: str | None
    cf_mitigated: str | None
    cf_ray: str | None
    error_body_sample: str | None
    """The first 4096 bytes of the body when `status >= 400`. None for other statuses."""


class ProbeFailed(_Frozen):
    """The probe could not do a stage for a local reason. This says nothing about the target."""

    outcome: Literal["probe_failed"] = "probe_failed"
    stage: Literal["dns", "tcp", "tls", "http"]
    detail: str


HttpsObservation = Annotated[
    DnsFailed | TcpFailed | TlsFailed | HttpFailed | HttpResponded | ProbeFailed,
    Field(discriminator="outcome"),
]
