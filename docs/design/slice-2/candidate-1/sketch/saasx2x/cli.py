"""Slice 2 additions to `src/saasx2x/cli.py`. One new command. Each slice 1 command stays.

saasx2x web             serve the dashboard and its API until stopped; never writes to Postgres
saasx2x web --openapi   print the OpenAPI document of the API and stop; needs no Postgres
"""

import argparse

from saasx2x.config import Settings


async def _run(args: argparse.Namespace, settings: Settings) -> int:
    # TODO: add this branch before the `async with Store.connect(...)` block, beside "check".
    # The web command does not use `Store`, so it has no path to a write method.
    #
    #   if args.command == "web":
    #       if args.openapi:
    #           print(openapi_document(settings))
    #           return 0
    #       await serve(settings)      # ReadStore.connect raises StoreUnavailable -> exit code 1
    #       return 0
    raise NotImplementedError


def _parser() -> argparse.ArgumentParser:
    # TODO:
    #   web = commands.add_parser("web", help="serve the read-only dashboard")
    #   web.add_argument("--openapi", action="store_true", help="print the API document and stop")
    raise NotImplementedError
