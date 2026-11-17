-- Migration 0001. Applied by Store.migrate() from migrations/0001_init.sql.
-- This file is the full slice 1 schema. Later slices add files, never edit this one.

create table account (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    created_at  timestamptz not null default now()
);

-- Slice 1 has one account. The CLI uses it when it is the only row.
insert into account (name) values ('owner');

create table target (
    id          uuid primary key default gen_random_uuid(),
    account_id  uuid not null references account (id),
    host        text not null
                check (host = lower(host) and host ~ '^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$'),
    created_at  timestamptz not null default now(),
    removed_at  timestamptz
);

-- A host is unique per account while it is active. A removed host can return.
create unique index target_active_host_uq
    on target (account_id, host) where removed_at is null;

-- One row per thing a probe does to a target. Slice 1 has one kind.
create table target_check (
    id          uuid primary key default gen_random_uuid(),
    target_id   uuid not null references target (id),
    kind        text not null check (kind in ('https_443')),
    interval_s  integer not null check (interval_s >= 60 and interval_s % 60 = 0),
    created_at  timestamptz not null default now(),
    unique (target_id, kind)
);

create table probe (
    id             text primary key check (id ~ '^[a-z0-9][a-z0-9-]{0,62}$'),
    region         text not null,
    registered_at  timestamptz not null default now()
);

-- One row per (check, probe, slot). The key makes a repeated run harmless.
-- Each probe writes only its own rows. Agreement across probes is a read-time join.
create table check_result (
    check_id       uuid not null references target_check (id),
    probe_id       text not null references probe (id),
    slot_start     timestamptz not null
                   check (extract(epoch from slot_start)::bigint % 60 = 0),
    started_at     timestamptz not null,
    finished_at    timestamptz not null,
    verdict        text not null,
    reason         text not null,
    rules_version  smallint not null,
    observation    jsonb not null
                   check (observation->>'phase' in ('tcp_failed', 'http_failed', 'http_responded')),
    primary key (check_id, probe_id, slot_start),
    check (finished_at >= started_at),
    -- Must equal the Reason enum in verdict.py. tests/test_schema_matches_enums.py enforces it.
    check ((verdict, reason) in (
        ('up',          'ok'),
        ('down',        'status_4xx'),
        ('down',        'status_5xx'),
        ('down',        'dns_failure'),
        ('down',        'tcp_refused'),
        ('down',        'tcp_timeout'),
        ('down',        'tcp_unreachable'),
        ('down',        'tls_failure'),
        ('down',        'http_timeout'),
        ('down',        'connection_reset'),
        ('down',        'http_protocol_error'),
        ('blocked',     'cloudflare_challenge'),
        ('probe_fault', 'probe_network_down')
    ))
);

-- Read path for later alert logic. It merges probes for one check and slot range.
create index check_result_slot_idx on check_result (check_id, slot_start desc);
