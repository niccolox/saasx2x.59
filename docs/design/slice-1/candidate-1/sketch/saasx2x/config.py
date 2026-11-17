"""Settings. The process environment is a boundary, so this module parses it one time."""

from datetime import timedelta
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from saasx2x.domain import AccountSlug, ProbeName
from saasx2x.https_check import Timeouts


class Settings(BaseSettings):
    """Each default works with `compose.yml` and no credentials."""

    model_config = SettingsConfigDict(env_prefix="SAASX2X_", frozen=True)

    database_url: str = "postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x"
    account: AccountSlug = AccountSlug("owner")
    probe_name: ProbeName = ProbeName("local")
    interval: timedelta = timedelta(seconds=300)
    max_concurrency: int = Field(default=20, ge=1)
    timeouts: Timeouts = Timeouts()
    ca_file: Path | None = None

    @model_validator(mode="after")
    def _one_check_fits_in_one_interval(self) -> "Settings":
        """Reject `timeouts.total_s >= interval`. A check must end before its slot ends."""
        raise NotImplementedError
