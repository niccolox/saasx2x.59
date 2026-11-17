"""Slice 2 additions to `cli.py`. Two new commands. The slice 1 commands stay.

saasx2x web       serve the dashboard and its JSON API on SAASX2X_WEB_HOST:SAASX2X_WEB_PORT
saasx2x schema    print the JSON schema of the API response, for the TypeScript generator

Neither command opens `Store`. `web` opens its own read-only `DashboardReader`. `schema` needs no
database. Both branches go before `async with Store.connect(...)` in `_run`, beside `check`.
"""

import argparse
import json

from saasx2x.config import Settings
from saasx2x.dashboard import dashboard_json_schema


async def _run(args: argparse.Namespace, settings: Settings) -> int:
    if args.command == "schema":
        print(json.dumps(dashboard_json_schema(), indent=2, sort_keys=True))
        return 0
    if args.command == "web":
        from saasx2x.web import serve  # the worker image path does not import FastAPI

        await serve(settings)
        return 0
    # ... slice 1 branches, unchanged ...
    raise NotImplementedError


def _add_slice_2_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    commands.add_parser("web", help="serve the read-only dashboard on 127.0.0.1:55441")
    commands.add_parser("schema", help="print the JSON schema of GET /api/dashboard")
