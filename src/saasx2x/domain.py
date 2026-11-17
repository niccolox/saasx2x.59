"""Domain types: what the probe checks, when, and what the probe saw. Pure, no I/O."""

import ipaddress
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, NewType, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    NonNegativeFloat,
    model_validator,
)

AccountSlug = NewType("AccountSlug", str)
AccountId = NewType("AccountId", UUID)
CheckId = NewType("CheckId", UUID)
ProbeId = NewType("ProbeId", str)

Hostname = NewType("Hostname", str)
"""A lowercase ASCII DNS name. Only `parse_hostname` makes one from owner input."""

Milliseconds = NonNegativeFloat

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MIN_INTERVAL = timedelta(seconds=60)

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def parse_hostname(raw: str) -> Hostname:
    """Parse owner input into a hostname. Raise ValueError for other input.

    Accept `Example.COM` and `example.com.`. Encode an international name with IDNA.
    Reject a scheme, a path, a port, and an IP literal. IP mode is a later slice.
    """
    text = raw.strip().rstrip(".")
    if any(c in text for c in "/:@?# "):
        raise ValueError(f"not a hostname (no scheme, path, or port): {raw!r}")
    try:
        ipaddress.ip_address(text)
    except ValueError:
        pass
    else:
        raise ValueError(f"an IP address is not a hostname: {raw!r}")
    try:
        ascii_name = text.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError(f"not a hostname: {raw!r}") from error
    if len(ascii_name) > 253 or not all(_LABEL.match(label) for label in ascii_name.split(".")):
        raise ValueError(f"not a hostname: {raw!r}")
    return Hostname(ascii_name)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CheckKind(StrEnum):
    HTTPS = "https"


class Slot(_Frozen):
    """One interval of a schedule, aligned to the Unix epoch in UTC.

    `start` is part of the key of a result row. The wall clock gives the slot, and no run gives
    the next one, so a schedule cannot drift.
    """

    start: AwareDatetime
    interval: timedelta

    @model_validator(mode="after")
    def _aligned_to_epoch(self) -> Self:
        if self.interval <= timedelta(0) or (self.start - EPOCH) % self.interval:
            raise ValueError(f"slot start {self.start} is not aligned to {self.interval}")
        return self

    @property
    def end(self) -> datetime:
        return self.start + self.interval

    def next(self) -> "Slot":
        return Slot(start=self.end, interval=self.interval)

    @classmethod
    def containing(cls, at: datetime, interval: timedelta) -> "Slot":
        return cls(start=EPOCH + ((at - EPOCH) // interval) * interval, interval=interval)


class SlotRange(_Frozen):
    """`count` slots in sequence. `first` is the oldest slot. A range can be empty."""

    first: Slot
    count: int = Field(ge=0)

    @property
    def start(self) -> datetime:
        return self.first.start

    @property
    def end(self) -> datetime:
        """The end of the last slot. Equal to `start` when the range is empty."""
        return self.first.start + self.count * self.first.interval

    def starts(self) -> Iterator[datetime]:
        """The start of each slot, oldest first."""
        return (self.first.start + n * self.first.interval for n in range(self.count))


def expected_slots(
    interval: timedelta, created_at: datetime, now: datetime, span: timedelta
) -> SlotRange:
    """The slots of the last `span` that the worker had to fill for one check.

    Let `open` be the slot that contains `now`. A slot is expected when all three are true:

    1. It started at or after `created_at`. The check existed for the whole slot.
    2. It ended at or before `now`. The worker cancels a check at slot end, so no row comes later.
    3. It started at or after `open.start - span`.

    A missing row in an expected slot is "not observed". A missing row in a different slot
    says nothing: the slot is outside the life of the check, or the slot is still open.
    The result depends only on the four arguments, so a count of expected slots needs no query.
    """
    open_slot = Slot.containing(now, interval)
    earliest = max(created_at, open_slot.start - span)
    first = Slot.containing(earliest, interval)
    if first.start < earliest:
        first = first.next()
    return SlotRange(first=first, count=max(0, (open_slot.start - first.start) // interval))


class ActiveCheck(_Frozen):
    """One check of a target that is not removed."""

    check_id: CheckId
    account_id: AccountId
    hostname: Hostname
    port: int = Field(ge=1, le=65535)
    interval: timedelta = Field(ge=MIN_INTERVAL)


Stage = Literal["dns", "tcp", "tls", "http"]
TcpError = Literal["refused", "timeout", "unreachable", "reset"]
TlsError = Literal["certificate_invalid", "handshake_failed", "timeout"]
HttpError = Literal["timeout", "connection_closed", "protocol_error"]


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
    error: TcpError


class _Connected(_Resolved):
    tcp_connect_ms: Milliseconds


class TlsFailed(_Connected):
    outcome: Literal["tls_failed"] = "tls_failed"
    error: TlsError
    detail: str
    """The message of the TLS library, for example "certificate has expired"."""


class _Secured(_Connected):
    tls_handshake_ms: Milliseconds


class HttpFailed(_Secured):
    outcome: Literal["http_failed"] = "http_failed"
    error: HttpError


BODY_HEAD_BYTES = 4096


class HttpResponded(_Secured):
    outcome: Literal["http_responded"] = "http_responded"
    http_ms: Milliseconds
    """Time from the first request byte to the last response header byte."""
    status: int = Field(ge=200, le=999)
    server: str | None
    cf_mitigated: str | None
    cf_ray: str | None
    body_head: str | None = Field(max_length=BODY_HEAD_BYTES)
    """The first BODY_HEAD_BYTES of the body when `status >= 400`, so a later rule can judge
    the row again. None for a lower status."""

    @model_validator(mode="after")
    def _body_head_only_for_errors(self) -> Self:
        if (self.body_head is None) != (self.status < 400):
            raise ValueError("body_head is present exactly when status >= 400")
        return self


class ProbeFailed(_Frozen):
    """The probe could not do a stage for a local reason. This says nothing about the target."""

    outcome: Literal["probe_failed"] = "probe_failed"
    stage: Stage
    detail: str


HttpsObservation = Annotated[
    DnsFailed | TcpFailed | TlsFailed | HttpFailed | HttpResponded | ProbeFailed,
    Field(discriminator="outcome"),
]
