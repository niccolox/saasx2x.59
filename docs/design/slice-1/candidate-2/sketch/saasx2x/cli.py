"""Command line. The process boundary: parses argv and environment, nothing else.

    saasx2x migrate
    saasx2x target add HOST [--path /healthz] [--account owner]
    saasx2x target remove HOST [--account owner]
    saasx2x target list [--account owner]
    saasx2x check HOST [--port 443] [--path /]   one observation, printed, not stored
    saasx2x worker                               migrate, register probe, run forever

Environment (parsed once into Settings):

    SAASX2X_DATABASE_URL   default postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x
    SAASX2X_PROBE_NAME     default "local"
    SAASX2X_PROBE_REGION   default "local"
    SAASX2X_MAX_IN_FLIGHT  default 32

Exit codes: 0 success, 2 bad input (parse_hostname or parse_path refused it),
1 any other error.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import Field

from saasx2x.domain import Frozen


class Settings(Frozen):
    database_url: str = "postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x"
    probe_name: str = "local"
    probe_region: str = "local"
    max_in_flight: int = Field(default=32, ge=1, le=1024)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        raise NotImplementedError


def main(argv: Sequence[str] | None = None) -> int:
    # TODO: argparse subcommands. Each one: Settings.from_env(os.environ),
    #       parse HOST with parse_hostname, open Store, call one Store or
    #       scheduler function, print a plain table, return an exit code.
    raise NotImplementedError
