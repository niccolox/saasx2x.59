"""Process settings from environment variables with prefix SAASX2X_. No secrets in code."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain import ProbeId


class Anchor(BaseModel):
    host: str
    port: int = 443


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAASX2X_", frozen=True)

    database_url: str = "postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x"
    probe_id: ProbeId = ProbeId("local-1")
    probe_region: str = "local"

    default_interval_s: int = Field(300, ge=60, multiple_of=60)  # used by `target add`
    tick_s: int = 60  # grid step of the scheduler. Every interval_s is a multiple of it.
    max_concurrency: int = Field(50, ge=1)

    tcp_timeout_s: float = 5.0
    https_timeout_s: float = 10.0  # connect, TLS, and full response read
    check_deadline_s: float = 20.0  # hard cap over TCP, HTTPS, and vantage together
    vantage_timeout_s: float = 3.0
    vantage_anchors: tuple[Anchor, ...] = (
        Anchor(host="one.one.one.one"),
        Anchor(host="dns.google"),
    )  # names, not IPs, so a broken resolver also reads as a probe fault

    ca_bundle: Path | None = None  # tests point this at the self-signed certificate
