"""Network I/O for one https_443 attempt. Returns domain Observation only.

httpx, ssl, and socket types stay inside this module. The User-Agent is a constant,
not a setting, because the product rule is one fixed User-Agent.
"""
from __future__ import annotations

from typing import Final, Protocol

from domain import Hostname, Observation
from settings import Settings

USER_AGENT: Final = "SaaSX2X-Monitor/0.1 (+https://saasx2x.example/bot)"
BODY_HEAD_BYTES: Final = 2048


class Prober(Protocol):
    async def observe(self, host: Hostname) -> Observation: ...


class NetworkProber:
    """Concrete Prober. One instance per worker. Holds the SSL context.

    observe():
      1. TCP: asyncio.open_connection(host, 443) under tcp_timeout_s. Time it. Close it.
         Failure becomes TcpErr and ends with vantage().
      2. HTTPS: one GET / with httpx. verify=True, follow_redirects=False, stream the body,
         read at most BODY_HEAD_BYTES. Failure becomes HttpErr and ends with vantage().
      3. Whole call runs under check_deadline_s. A deadline hit maps to the phase that was open.
    The TCP phase and the HTTPS phase use two connections. This is deliberate.
    """

    def __init__(self, settings: Settings) -> None:
        raise NotImplementedError

    async def observe(self, host: Hostname) -> Observation:
        raise NotImplementedError

    async def _vantage(self) -> str:
        """Try TCP connect to every anchor at once. 'reachable' if any connects, else 'unreachable'."""
        raise NotImplementedError
