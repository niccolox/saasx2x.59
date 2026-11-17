"""Slice 2 additions to `src/saasx2x/domain.py`. Append them. Each existing name stays as it is.

Pure, no I/O. `expected_slots` is the one owner of the rule "which slots must have a row".
No SQL and no TypeScript repeats this rule.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta

from pydantic import Field

from saasx2x.domain import Slot, _Frozen  # local names in the real file


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
        raise NotImplementedError


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
    # TODO:
    #   open = Slot.containing(now, interval)
    #   earliest = max(created_at, open.start - span)
    #   first = Slot.containing(earliest, interval)
    #   if first.start < earliest: first = first.next()
    #   count = max(0, (open.start - first.start) // interval)
    #   return SlotRange(first=first, count=count)
    raise NotImplementedError
