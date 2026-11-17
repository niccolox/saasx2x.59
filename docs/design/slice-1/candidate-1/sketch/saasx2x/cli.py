"""The command line. Thin: parse the arguments, call one function, print the result.

    saasx2x migrate
    saasx2x target add HOSTNAME
    saasx2x target remove HOSTNAME
    saasx2x target list
    saasx2x check HOSTNAME        one check now; print the observation and the verdict; no row
    saasx2x worker                run the schedule until stopped
"""

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Return the exit code. 0: done. 2: input that `parse_hostname` rejects."""
    # settings = Settings()
    # hostname = parse_hostname(args.hostname)          # the only place that parses owner input
    # target add    -> store.add_target(settings.account, hostname)
    # target remove -> store.remove_target(settings.account, hostname)
    # target list   -> store.list_targets(settings.account)
    # check         -> observation = await check_https(hostname, 443, tls=..., timeouts=...)
    #                  print(observation.model_dump_json(), decide_verdict(observation))
    # worker        -> await run_worker(store, settings)
    raise NotImplementedError
