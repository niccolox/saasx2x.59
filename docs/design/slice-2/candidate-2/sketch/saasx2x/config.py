"""Slice 2 additions to `config.py`. Two new settings. The slice 1 settings stay."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from saasx2x.domain import AccountSlug, ProbeId


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAASX2X_", frozen=True)

    database_url: str = "postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x"
    probe_id: ProbeId = Field(default=ProbeId("local-1"), pattern=r"^[a-z0-9][a-z0-9-]*$")
    account: AccountSlug = AccountSlug("owner")
    max_concurrency: int = Field(default=20, ge=1)

    web_host: str = "127.0.0.1"
    """The address of `saasx2x web`. On the host, keep the default. In the Compose `web`
    service it is `0.0.0.0` inside the container, and the port publish binds 127.0.0.1 on the
    host. A test reads `compose.yml` and fails if the publish is not on 127.0.0.1."""
    web_port: int = Field(default=55441, ge=1, le=65535)
