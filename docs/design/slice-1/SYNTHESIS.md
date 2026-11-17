# Slice 1 synthesis: the design contract

Base: candidate 1 (`candidate-1/`). Use its `RATIONALE.md`, `MODULE_MAP.md`, `schema.sql`, and `sketch/saasx2x/*.py` as the starting contract. The changes below override candidate 1 where they differ. Do not take other parts of candidates 2 and 3.

No cross-judge ran: every available model is from one vendor (Anthropic), and the arena skill forbids a same-vendor judge.

## Scores

| Rubric item | C1 | C2 | C3 |
| --- | --- | --- | --- |
| Verdict separates down, blocked, probe fault; no illegal states | 5 | 4 | 5 |
| Accounts and regions later with no rewrite | 4 | 5 | 4 |
| Fixed-rate scheduler, bounded, idempotent | 4 | 5 | 4 |
| Pure verdict, short call chain | 5 | 4 | 4 |
| Smallest slice-1 code | 4 | 3 | 4 |

## Convergence (all three agree, so keep without debate)

- Postgres tables are the only target list. The CLI `saasx2x target add|remove|list` writes them. Remove sets `removed_at`.
- One pure verdict function. The verdict is derived from the stored observation, never passed in. `rules_version` on every row.
- Result key is (check, slot, probe). Slot is aligned to the epoch in UTC. Insert with `ON CONFLICT DO NOTHING`. A missing row means "not observed".
- No redirects followed. No ICMP. No retry inside a slot.
- Plain SQL migrations applied in name order under an advisory lock with a sha256 check. No Alembic.
- Observation stored as JSONB, with typed columns for what queries need.
- A test fails when Python enums and SQL enums differ.

## Grafts

1. **Per-check offset inside the slot (from C2).** A check is due at `slot_start + offset(check_id)`. The offset is a blake2b hash of the check id, in `[0, interval_s - 40 s)`. Offsets spread the load, and later probes in other regions check one target at the same instant. Store `due_at` and `started_at` on each row. On restart, run a missing check of the current slot at once if the slot has at least 30 s left. Cancel a check that is not done at slot end, and write no row for it (from C1).
2. **`account_id` on `check_results` with a composite foreign key (from C2).** `checks` has a unique `(id, account_id)`. `check_results (check_id, account_id)` references it. Later row security then needs no join.
3. **A typed `reason` column (from C3).** Each `Reason` enum member owns its `Verdict`, so a reason and a verdict cannot disagree. Store `reason` beside `verdict`. A SQL CHECK lists the valid pairs, and the enum sync test covers it.
4. **Body head kept for replay (from C3).** For status 400 and above, store the first 4096 bytes of the body in the observation, so a rule change can judge old rows again.

## Product defaults chosen by the orchestrator

The owner can change these later. Each one is a constant in `verdict.py` with a test.

| Answer | Verdict | Why |
| --- | --- | --- |
| `cf-mitigated: challenge`, any status | blocked | The stable Cloudflare signal |
| `server: cloudflare`, status 403, 429, or 503, and a challenge or block marker in the first 4096 body bytes | blocked | C1 rule |
| Any status 429 | blocked | The server answered and rate-limits the probe. A 429 is not an outage. |
| 200 to 399 | up | |
| 401 | up | The server answered and asks for a login. The owner's apps may sit behind a login at `/`. |
| Any other status | down | |
| DNS not found, TCP failed, TLS failed, HTTP failed | down | |
| DNS unavailable, local socket error | inconclusive | C1 rule. No evidence about the target. |

Timeouts: DNS 5 s, TCP 5 s, TLS 5 s, HTTP 15 s. Whole check at most 30 s. Body read stops at 4096 bytes.

User-Agent constant: `SaaSX2X-Monitor/0.1 (+https://github.com/niccolox/saasx2x)`.

## Fixed project facts

- Repository root: `/home/niccolox/Projects/saasx2x.59`. Package `saasx2x` under `src/`. Tests under `tests/`. Migrations under `migrations/`.
- Python 3.13 with `uv` (`requires-python = ">=3.13"`). Pydantic v2, `psycopg` 3, `h11`. Dev: `pytest`, `pytest-asyncio`, `ruff`, `pyright`.
- `compose.yml` with service `db` (postgres:16, host port `127.0.0.1:55440`, named volume) and service `worker` (builds the package, `restart: unless-stopped`, runs `saasx2x worker`).
- Settings from environment variables with a `SAASX2X_` prefix. `SAASX2X_DATABASE_URL` default `postgresql://saasx2x:saasx2x@127.0.0.1:55440/saasx2x`. `SAASX2X_PROBE_ID` default `local-1`.
- `checks.interval_s` with default 300 and a CHECK of at least 60. `target add --interval 60` sets it, so a live test does not wait 5 minutes.
