-- SaaSX2X slice 1 schema. This file is the content of migrations/0001_init.sql.
-- Postgres 16. Each time value is timestamptz in UTC.

-- tests/test_schema.py compares these two types with the Python enums. A difference fails the build.
CREATE TYPE verdict AS ENUM ('up', 'down', 'blocked', 'inconclusive');
CREATE TYPE check_kind AS ENUM ('https');

CREATE TABLE accounts (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        text NOT NULL UNIQUE CHECK (slug <> ''),
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- One site of one account. `target remove` sets removed_at. No command deletes a row,
-- so a target keeps its id and its results when the owner adds it again.
CREATE TABLE targets (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  uuid NOT NULL REFERENCES accounts (id),
    hostname    text NOT NULL CHECK (hostname <> '' AND hostname = lower(hostname)),
    created_at  timestamptz NOT NULL DEFAULT now(),
    removed_at  timestamptz,
    UNIQUE (account_id, hostname)
);

-- One thing that a probe measures on a target. Slice 1 has one row for each target: https on 443.
-- A later check type adds a value to check_kind and a row here. The key of check_results stays.
CREATE TABLE checks (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id   uuid NOT NULL REFERENCES targets (id),
    kind        check_kind NOT NULL,
    port        integer NOT NULL CHECK (port BETWEEN 1 AND 65535),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (target_id, kind, port)
);

-- One process that makes checks from one network location. Slice 1 has one row.
CREATE TABLE probes (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE CHECK (name <> ''),
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- One row for each (check, slot, probe). Insert only. No statement updates or deletes a row.
--
-- The key is the identity of the work, not of the attempt. A second run of the same check in
-- the same slot conflicts on the key, and the store keeps the first row.
--
-- A slot with no row means "the probe did not check". It does not mean "down".
--
-- Key order (check_id, scheduled_at, probe_id) gives, with no other index:
--   the history of one check in time order,
--   all probes of one check in one slot, for the later agreement rule,
--   the lookup that Store.due_checks does.
CREATE TABLE check_results (
    check_id       uuid NOT NULL REFERENCES checks (id),
    scheduled_at   timestamptz NOT NULL,           -- Slot.start
    probe_id       uuid NOT NULL REFERENCES probes (id),
    started_at     timestamptz NOT NULL,           -- when the probe started the check
    duration_ms    double precision NOT NULL CHECK (duration_ms >= 0),
    verdict        verdict NOT NULL,               -- decide_verdict(observation) at write time
    rules_version  smallint NOT NULL,              -- the RULES_VERSION that gave the verdict
    observation    jsonb NOT NULL CHECK (observation ? 'outcome'),
                                                   -- the Pydantic JSON of HttpsObservation
    PRIMARY KEY (check_id, scheduled_at, probe_id)
);
