# SaaSX2X

SaaSX2X is an uptime monitor. Slice 1 checks each target on port 443 at a fixed interval and writes one row for each result to Postgres. A check is one connection: DNS, TCP, TLS, then `GET /`. Slice 2 adds a read-only dashboard. [PRODUCT.md](PRODUCT.md) records the product. [docs/design/slice-1/SYNTHESIS.md](docs/design/slice-1/SYNTHESIS.md) and [docs/design/slice-2/SYNTHESIS.md](docs/design/slice-2/SYNTHESIS.md) record the design.

## Start

You need Docker and [uv](https://docs.astral.sh/uv/).

```sh
docker compose up -d db
uv sync
uv run saasx2x migrate
```

Run the worker on the host, or in Compose:

```sh
uv run saasx2x worker              # stop with Ctrl-C
docker compose up -d worker        # restart: unless-stopped
```

## Add a target

```sh
uv run saasx2x target add example.com                 # every 300 s, port 443
uv run saasx2x target add example.com --interval 60   # change the interval (at least 60 s)
uv run saasx2x target list
uv run saasx2x target remove example.com              # stops the checks, keeps the results
uv run saasx2x check example.com                      # one check now, writes no row
```

## Dashboard

The dashboard is one read-only page at http://127.0.0.1:55441/. For each target, it shows the last result, a strip of the last 24 hours, and the uptime for 24 hours and 7 days. A slot with no row shows as "not observed". The line at the top shows at once when the worker stops writing rows.

Run it in Compose. The image builds the page, so the host needs no Node:

```sh
docker compose up -d web
```

To read a different database, set `SAASX2X_WEB_DATABASE_URL`. Compose gives it to the container as `SAASX2X_DATABASE_URL`, so the host name is `db`:

```sh
SAASX2X_WEB_DATABASE_URL=postgresql://saasx2x:saasx2x@db:5432/saasx2x_live docker compose up -d web
```

Or run it on the host. Build the page one time with Node 26 and npm:

```sh
npm --prefix web ci
npm --prefix web run build
uv run saasx2x web                 # http://127.0.0.1:55441/, stop with Ctrl-C
```

The web process never writes to Postgres and never runs `migrate`. Until the worker runs `migrate`, the page shows a 503 message. The process binds 127.0.0.1 only and has no sign-in.

To change the page with live reload, run `uv run saasx2x web` and `npm --prefix web run dev`, then open http://127.0.0.1:5173/. After a change to `src/saasx2x/dashboard.py`, run `uv run saasx2x web --openapi > web/openapi.json`. A test fails until you do.

## Read the results with SQL

```sh
docker compose exec db psql -U saasx2x -d saasx2x
```

```sql
SELECT t.hostname, c.port, r.scheduled_at, r.started_at, r.verdict, r.reason,
       round(r.duration_ms) AS ms, r.observation->>'status' AS status
  FROM check_results r
  JOIN checks c ON c.id = r.check_id
  JOIN targets t ON t.id = c.target_id
 ORDER BY r.scheduled_at DESC, t.hostname
 LIMIT 20;
```

`verdict` is `up`, `down`, `blocked` (a Cloudflare challenge or a rate limit), or `inconclusive` (the probe itself failed). `reason` names the rule that gave the verdict. `observation` holds what the probe saw. A slot with no row means that the probe did not check.

## Settings

| Variable | Default |
| --- | --- |
| `SAASX2X_DATABASE_URL` | `postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x` |
| `SAASX2X_PROBE_ID` | `local-1` |
| `SAASX2X_ACCOUNT` | `owner` |
| `SAASX2X_MAX_CONCURRENCY` | `20` |
| `SAASX2X_WEB_HOST` | `127.0.0.1` |
| `SAASX2X_WEB_PORT` | `55441` |

## Develop

```sh
uv run ruff check .
uv run pyright
uv run pytest -q     # needs `docker compose up -d db`; tests use their own scratch databases
npm --prefix web ci && npm --prefix web test   # tsc and vitest
```

`tests/test_browser.py` drives Chromium. It skips until you build the page and run `uv run playwright install chromium` one time.
