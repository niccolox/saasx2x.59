"""Settings. The process environment is a boundary, so this module parses it one time."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from saasx2x.domain import AccountSlug, ProbeId


class Settings(BaseSettings):
    """Each default works with `compose.yml` and no credentials."""

    model_config = SettingsConfigDict(env_prefix="SAASX2X_", frozen=True)

    database_url: str = "postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x"
    probe_id: ProbeId = Field(default=ProbeId("local-1"), pattern=r"^[a-z0-9][a-z0-9-]*$")
    account: AccountSlug = AccountSlug("owner")
    max_concurrency: int = Field(default=20, ge=1)
    web_host: str = "127.0.0.1"
    """The address that `saasx2x web` binds. Compose sets 0.0.0.0 inside the container only.
    The Compose port map binds the host side to 127.0.0.1."""
    web_port: int = Field(default=55441, ge=1, le=65535)
