"""Result rows for the dashboard tests, written through `Store` the way the worker writes them."""

from datetime import datetime, timedelta
from ipaddress import ip_address

import psycopg

from saasx2x.domain import ActiveCheck, HttpResponded, HttpsObservation, ProbeId, TcpFailed
from saasx2x.verdict import CheckResult

PROBE = ProbeId("test-probe")
STARTED_AFTER = timedelta(seconds=1)
DURATION = timedelta(milliseconds=250)

UP = HttpResponded(
    ip=ip_address("192.0.2.1"),
    dns_ms=1,
    tcp_connect_ms=1,
    tls_handshake_ms=1,
    http_ms=1,
    status=200,
    server=None,
    cf_mitigated=None,
    cf_ray=None,
    body_head=None,
)
TCP_REFUSED = TcpFailed(ip=ip_address("192.0.2.1"), dns_ms=1, error="refused")


def result_at(
    check: ActiveCheck,
    slot_start: datetime,
    observation: HttpsObservation = UP,
    probe: ProbeId = PROBE,
) -> CheckResult:
    """The row of one check that started 1 s into its slot and took 250 ms."""
    return CheckResult(
        check_id=check.check_id,
        account_id=check.account_id,
        probe_id=probe,
        scheduled_at=slot_start,
        due_at=slot_start,
        started_at=slot_start + STARTED_AFTER,
        duration_ms=DURATION / timedelta(milliseconds=1),
        observation=observation,
    )


async def make_check_older(database_url: str, check: ActiveCheck, created_at: datetime) -> None:
    """`add_target` sets `created_at` to the real time. The tests need a fixed time."""
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as db:
        await db.execute(
            "UPDATE checks SET created_at = %s WHERE id = %s", (created_at, check.check_id)
        )
