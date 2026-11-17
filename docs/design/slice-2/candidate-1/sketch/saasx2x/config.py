"""Slice 2 additions to `Settings` in `src/saasx2x/config.py`. Add the two fields."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAASX2X_", frozen=True)

    # ... the slice 1 fields stay as they are ...

    web_host: str = "127.0.0.1"
    """The address that `saasx2x web` binds. Compose sets 0.0.0.0 inside the container only.
    The Compose port map binds the host side to 127.0.0.1."""
    web_port: int = Field(default=55441, ge=1, le=65535)
