-- SaaSX2X slice 1 schema. Ships as migrations/0001_init.sql.
-- Every enum below mirrors a Python StrEnum. tests/test_schema_sync.py reads
-- pg_enum and information_schema and fails when they differ from the domain.

create type check_kind as enum ('https');
create type stage as enum ('dns', 'tcp', 'tls', 'http');
create type failure_reason as enum (
    'nxdomain', 'dns_temporary', 'dns_no_address', 'timeout', 'refused',
    'host_unreachable', 'no_route', 'reset', 'tls_cert_invalid',
    'tls_handshake', 'bad_response', 'closed', 'local_resource', 'probe_internal'
);
create type verdict as enum ('up', 'down', 'blocked', 'probe_error');
create type block_signal as enum (
    'cf_mitigated_challenge', 'cf_challenge_page', 'cf_block_page', 'rate_limited'
);

-- store.migrate() creates schema_migration itself before it applies this file.

create table account (
    id         bigint generated always as identity primary key,
    slug       text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{0,62}$'),
    created_at timestamptz not null default now()
);

-- Stage 1 has one account. Stage 2 adds rows here, not a new model.
insert into account (slug) values ('owner');

create table target (
    id         bigint generated always as identity primary key,
    account_id bigint not null references account (id),
    hostname   text not null
               check (hostname = lower(hostname) and length(hostname) between 1 and 253),
    created_at timestamptz not null default now(),
    removed_at timestamptz,
    unique (account_id, hostname),
    unique (id, account_id)
);

-- "check" is a reserved word, so the table is target_check.
create table target_check (
    id         bigint generated always as identity primary key,
    account_id bigint not null,
    target_id  bigint not null,
    kind       check_kind not null default 'https',
    port       integer not null default 443 check (port between 1 and 65535),
    path       text not null default '/'
               check (path like '/%' and octet_length(path) <= 2048),
    interval_s integer not null default 300
               check (interval_s between 60 and 86400 and 86400 % interval_s = 0),
    created_at timestamptz not null default now(),
    foreign key (target_id, account_id) references target (id, account_id),
    unique (target_id, kind, port),
    unique (id, account_id)
);

create table probe (
    id         integer generated always as identity primary key,
    name       text not null unique,
    region     text not null,
    created_at timestamptz not null default now()
);

-- One row per (check, slot, probe). Facts first, then the judgment of those
-- facts under rules_version. Append-only: the worker never updates a row.
create table check_result (
    check_id       bigint not null,
    slot_start     timestamptz not null,
    probe_id       integer not null references probe (id),
    account_id     bigint not null,

    due_at         timestamptz not null,
    started_at     timestamptz not null,

    remote_addr    inet,
    dns_ms         integer check (dns_ms >= 0),
    tcp_ms         integer check (tcp_ms >= 0),
    tls_ms         integer check (tls_ms >= 0),
    http_ms        integer check (http_ms >= 0),
    total_ms       integer not null check (total_ms >= 0),
    http_status    smallint check (http_status between 100 and 599),
    failed_stage   stage,
    failure_reason failure_reason,
    detail         text check (length(detail) <= 200),

    verdict        verdict not null,
    block_signal   block_signal,
    rules_version  smallint not null,

    primary key (check_id, slot_start, probe_id),
    foreign key (check_id, account_id) references target_check (id, account_id),

    check (extract(epoch from slot_start)::bigint % 60 = 0),
    check (due_at >= slot_start),
    -- The ladder: a stage time exists only if every earlier stage time exists.
    check (tcp_ms is null or dns_ms is not null),
    check (tls_ms is null or tcp_ms is not null),
    check (http_ms is null or tls_ms is not null),
    check ((http_status is null) = (http_ms is null)),
    check (remote_addr is null or dns_ms is not null),
    -- The end: an HTTP answer, or a stop at one stage for one reason. Never both.
    check ((failed_stage is null) = (failure_reason is null)),
    check ((failed_stage is null) = (http_status is not null)),
    -- The judgment.
    check ((verdict = 'blocked') = (block_signal is not null)),
    check (verdict not in ('up', 'blocked') or http_status is not null)
);

-- worker restart: "which keys did this probe write since T".
-- Later: "what did probe P see in slot S" for probe health and agreement.
create index check_result_probe_slot on check_result (probe_id, slot_start);
