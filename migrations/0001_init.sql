CREATE TYPE verdict AS ENUM ('up', 'down', 'blocked', 'inconclusive');
CREATE TYPE check_kind AS ENUM ('https');
CREATE TYPE reason AS ENUM (
    'cloudflare_challenge', 'cloudflare_block_page', 'rate_limited',
    'status_ok', 'login_required', 'error_status',
    'dns_not_found', 'tcp_failed', 'tls_failed', 'http_failed',
    'dns_unavailable', 'probe_failed'
);

CREATE TABLE accounts (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        text NOT NULL UNIQUE CHECK (slug <> ''),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE targets (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  uuid NOT NULL REFERENCES accounts (id),
    hostname    text NOT NULL CHECK (hostname <> '' AND hostname = lower(hostname)),
    created_at  timestamptz NOT NULL DEFAULT now(),
    removed_at  timestamptz,
    UNIQUE (account_id, hostname),
    UNIQUE (id, account_id)
);

CREATE TABLE checks (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id   uuid NOT NULL,
    account_id  uuid NOT NULL,
    kind        check_kind NOT NULL,
    port        integer NOT NULL CHECK (port BETWEEN 1 AND 65535),
    interval_s  integer NOT NULL DEFAULT 300 CHECK (interval_s >= 60),
    created_at  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (target_id, account_id) REFERENCES targets (id, account_id),
    UNIQUE (target_id, kind, port),
    UNIQUE (id, account_id)
);

CREATE TABLE probes (
    id          text PRIMARY KEY CHECK (id ~ '^[a-z0-9][a-z0-9-]*$'),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE check_results (
    check_id       uuid NOT NULL,
    scheduled_at   timestamptz NOT NULL,
    probe_id       text NOT NULL REFERENCES probes (id),
    account_id     uuid NOT NULL,
    due_at         timestamptz NOT NULL,
    started_at     timestamptz NOT NULL,
    duration_ms    double precision NOT NULL CHECK (duration_ms >= 0),
    verdict        verdict NOT NULL,
    reason         reason NOT NULL,
    rules_version  smallint NOT NULL,
    observation    jsonb NOT NULL CHECK (observation ? 'outcome'),
    PRIMARY KEY (check_id, scheduled_at, probe_id),
    FOREIGN KEY (check_id, account_id) REFERENCES checks (id, account_id),
    CHECK (due_at >= scheduled_at),
    CHECK ((verdict, reason) IN (
        ('blocked',      'cloudflare_challenge'),
        ('blocked',      'cloudflare_block_page'),
        ('blocked',      'rate_limited'),
        ('up',           'status_ok'),
        ('up',           'login_required'),
        ('down',         'error_status'),
        ('down',         'dns_not_found'),
        ('down',         'tcp_failed'),
        ('down',         'tls_failed'),
        ('down',         'http_failed'),
        ('inconclusive', 'dns_unavailable'),
        ('inconclusive', 'probe_failed')
    ))
);
