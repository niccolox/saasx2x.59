"""The verdict rules. Pure. This module is the only place that knows what "up" means."""

from enum import StrEnum
from typing import Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, computed_field

from saasx2x.domain import CheckId, HttpResponded, HttpsObservation, Milliseconds, ProbeId


class Verdict(StrEnum):
    UP = "up"
    DOWN = "down"
    BLOCKED = "blocked"
    """Cloudflare refused or challenged the probe. Not a down state. Sends no down alert."""
    INCONCLUSIVE = "inconclusive"
    """The check gave no evidence about the target. Not a down state."""


RULES_VERSION: Final = 1
"""Increase this number with each change to `decide_verdict`. Each result row records it."""

_CLOUDFLARE_BLOCK_STATUSES: Final = frozenset({403, 429, 503})
_CLOUDFLARE_BLOCK_MARKERS: Final = (
    "<title>Just a moment...</title>",
    "/cdn-cgi/challenge-platform/",
    "<title>Attention Required! | Cloudflare</title>",
    "error code: 10",
)


def decide_verdict(observation: HttpsObservation) -> Verdict:
    """Map one observation to one verdict. Total and pure.

    | Observation                                   | Verdict      |
    | --------------------------------------------- | ------------ |
    | DnsFailed(not_found)                          | down         |
    | DnsFailed(unavailable)                        | inconclusive |
    | TcpFailed(any error)                          | down         |
    | TlsFailed(any error)                          | down         |
    | HttpFailed(any error)                         | down         |
    | HttpResponded, `_is_cloudflare_block` is true | blocked      |
    | HttpResponded, status 200 to 399              | up           |
    | HttpResponded, status 400 to 599              | down         |
    | ProbeFailed                                   | inconclusive |

    The Cloudflare row comes before the status rows.
    """
    # TODO: `match observation:` with one `case` for each class, then `assert_never`.
    #       A new class in the union then fails the type check until it has a verdict.
    raise NotImplementedError


def _is_cloudflare_block(response: HttpResponded) -> bool:
    """True when the Cloudflare edge made the response to refuse or challenge the probe.

    Rule 1: `cf-mitigated: challenge` is present. The status does not matter.
    Rule 2: `server` is `cloudflare`, the status is 403, 429 or 503, and
            `error_body_sample` contains one of `_CLOUDFLARE_BLOCK_MARKERS`.

    `server: cloudflare` alone is not sufficient. Cloudflare puts that header on each response
    that it proxies, so an origin 503 has it too. An origin 503 is "down".
    """
    raise NotImplementedError


class CheckResult(BaseModel):
    """One row of `check_results`: an observation, who made it, when, and its verdict.

    `verdict` derives from `observation`. A result with a verdict that disagrees with its
    observation is not representable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: CheckId
    probe_id: ProbeId
    scheduled_at: AwareDatetime
    """`Slot.start`. With `check_id` and `probe_id`, the identity of the row."""
    started_at: AwareDatetime
    duration_ms: Milliseconds
    observation: HttpsObservation

    @computed_field
    @property
    def verdict(self) -> Verdict:
        raise NotImplementedError

    @computed_field
    @property
    def rules_version(self) -> int:
        raise NotImplementedError
