"""The command line. Thin: parse the arguments, call one function, print the result.

saasx2x migrate
saasx2x target add HOSTNAME [--port 443] [--interval 300]
saasx2x target remove HOSTNAME
saasx2x target list
saasx2x check HOSTNAME [--port 443]   one check now; print the observation; write no row
saasx2x worker                        run the schedule until stopped
saasx2x web                           serve the dashboard until stopped; never writes to Postgres
saasx2x web --openapi                 print the OpenAPI document of the API; needs no Postgres
"""

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Sequence
from datetime import timedelta

from saasx2x.config import Settings
from saasx2x.domain import MIN_INTERVAL, ActiveCheck, Hostname, HttpsObservation, parse_hostname
from saasx2x.https_check import Timeouts, check_https, tls_context
from saasx2x.store import Store, StoreUnavailable
from saasx2x.verdict import decide_verdict
from saasx2x.web import openapi_document, serve
from saasx2x.worker import run_worker


def main(argv: Sequence[str] | None = None) -> int:
    """Return the exit code. 0: done. 1: Postgres is not available. 2: bad input.

    `saasx2x web` exits with code 3 when it cannot start. Uvicorn logs the cause.
    """
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_run(args, Settings()))
    except StoreUnavailable as error:
        print(f"saasx2x: Postgres is not available: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


async def _run(args: argparse.Namespace, settings: Settings) -> int:
    if args.command == "check":
        hostname: Hostname = args.hostname
        observation = await check_https(hostname, args.port, tls=tls_context(), timeouts=Timeouts())
        reason = decide_verdict(observation)
        print(observation.model_dump_json(indent=2))
        print(f"verdict: {reason.verdict} ({reason})")
        return 0

    if args.command == "web":
        if args.openapi:
            print(openapi_document(settings))
            return 0
        await serve(settings)
        return 0

    async with Store.connect(settings.database_url) as store:
        match args.command, getattr(args, "action", None):
            case "migrate", _:
                applied = await store.migrate()
                print("\n".join(f"applied {name}" for name in applied) or "nothing to apply")
            case "target", "add":
                interval = timedelta(seconds=args.interval)
                check = await store.add_target(
                    settings.account, args.hostname, port=args.port, interval=interval
                )
                print(f"added {_describe(check)}")
            case "target", "remove":
                removed = await store.remove_target(settings.account, args.hostname)
                print(f"removed {args.hostname}" if removed else f"{args.hostname} is not active")
            case "target", "list":
                for check in await store.list_targets(settings.account):
                    print(_describe(check))
            case _:
                _log_in_utc()
                await store.register_probe(settings.probe_id)
                tls, timeouts = tls_context(), Timeouts()

                async def observe(check: ActiveCheck) -> HttpsObservation:
                    return await check_https(check.hostname, check.port, tls=tls, timeouts=timeouts)

                logging.info("worker %s started", settings.probe_id)
                await run_worker(
                    store, settings.probe_id, observe, max_concurrency=settings.max_concurrency
                )
    return 0


def _log_in_utc() -> None:
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def _describe(check: ActiveCheck) -> str:
    return f"{check.hostname}:{check.port} every {check.interval.total_seconds():.0f} s"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="saasx2x", description="SaaSX2X uptime monitor")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply the SQL files in migrations/")
    commands.add_parser("worker", help="run the schedule until stopped")
    check = commands.add_parser("check", help="check one host now and write no row")
    check.add_argument("hostname", type=_hostname)
    check.add_argument("--port", type=_port, default=443)

    web = commands.add_parser("web", help="serve the read-only dashboard until stopped")
    web.add_argument("--openapi", action="store_true", help="print the API document and stop")

    target = commands.add_parser("target", help="add, remove, or list targets")
    actions = target.add_subparsers(dest="action", required=True)
    add = actions.add_parser("add", help="monitor a host, or change its interval")
    add.add_argument("hostname", type=_hostname)
    add.add_argument("--port", type=_port, default=443)
    add.add_argument("--interval", type=_interval_s, default=300, help="seconds, at least 60")
    remove = actions.add_parser("remove", help="stop the checks of a host and keep its results")
    remove.add_argument("hostname", type=_hostname)
    actions.add_parser("list", help="show the active checks")
    return parser


def _hostname(raw: str) -> Hostname:
    try:
        return parse_hostname(raw)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _port(raw: str) -> int:
    port = int(raw)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port must be from 1 to 65535: {raw}")
    return port


def _interval_s(raw: str) -> int:
    seconds = int(raw)
    if seconds < MIN_INTERVAL.total_seconds():
        raise argparse.ArgumentTypeError(f"interval must be at least 60 seconds: {raw}")
    return seconds
