"""ADDITIONS to src/saasx2x/config.py and src/saasx2x/cli.py. Not a module.

---- config.py: two fields on `Settings` ----

    web_host: str = "127.0.0.1"
    web_port: int = Field(default=55441, ge=1, le=65535)

Environment: SAASX2X_WEB_HOST, SAASX2X_WEB_PORT. The default binds loopback only.
`compose.yml` sets SAASX2X_WEB_HOST=0.0.0.0 INSIDE the container, because a port mapping cannot
reach a container that listens on 127.0.0.1. The host side of the mapping stays on 127.0.0.1.
A test reads compose.yml and fails if the `web` ports entry does not start with "127.0.0.1:".

---- cli.py: one command ----

Docstring: add the line
    saasx2x web                           serve the status page and its JSON until stopped

`_parser()`: add
    commands.add_parser("web", help="serve the read-only status page")

`_run()`: add this branch BEFORE `async with Store.connect(...)`, because `web` opens a read-only
store, not the read-write store:

    if args.command == "web":
        _log_in_utc()
        await serve(settings)          # from saasx2x.web
        return 0

No new exit code. `StoreUnavailable` at start cannot happen (the pool connects in the background).
"""
