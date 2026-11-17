"""Slice 2 addition to `src/saasx2x/verdict.py`. Append it. Each existing rule stays as it is.

`RULES_VERSION` does not change: no stored value depends on `fold_probes`.
"""

from collections.abc import Sequence
from typing import Final

from saasx2x.verdict import Reason, Verdict  # local names in the real file

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

    One row gives that row. Slice 2 has one probe, so only that case occurs in production.
    The other cases have tests, so a second probe needs no change to the store, the API, or
    the page.
    """
    raise NotImplementedError
