-- Ops Warehouse Schema
--
-- Formalizes platform operational data into a queryable Postgres schema.
-- Tables are populated by the Dockhand infra-agent ETL workflow
-- (ops_warehouse_etl) running on a 6-hour schedule.
--
-- See: docs/plans/dash-integration-roadmap.md (Phase 0)

-- ============================================================
-- Core: What exists and what should exist
-- ============================================================

CREATE TABLE IF NOT EXISTS desired_services (
    id              SERIAL PRIMARY KEY,
    app_name        TEXT NOT NULL,
    service_name    TEXT NOT NULL,
    environment     TEXT NOT NULL,
    image           TEXT,
    image_tag       TEXT,
    domains         TEXT[],
    traefik_labels  JSONB,
    volumes         TEXT[],
    networks        TEXT[],
    source_file     TEXT NOT NULL,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS actual_services (
    id              SERIAL PRIMARY KEY,
    snapshot_id     TEXT NOT NULL,
    service_name    TEXT NOT NULL,
    host            TEXT NOT NULL,
    image           TEXT,
    image_tag       TEXT,
    replicas        TEXT,
    state           TEXT,
    ports           TEXT[],
    networks        TEXT[],
    created_at      TIMESTAMPTZ,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Drift: The delta between desired and actual
-- ============================================================

CREATE TABLE IF NOT EXISTS drift_observations (
    id              SERIAL PRIMARY KEY,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category        TEXT NOT NULL,
    severity        TEXT NOT NULL,
    service_name    TEXT,
    desired_value   TEXT,
    actual_value    TEXT,
    description     TEXT NOT NULL,
    blast_radius    INTEGER DEFAULT 1,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolution      TEXT
);

-- ============================================================
-- Events: What happened and when
-- ============================================================

CREATE TABLE IF NOT EXISTS deploy_events (
    id              SERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,
    app_name        TEXT NOT NULL,
    environment     TEXT NOT NULL,
    image_before    TEXT,
    image_after     TEXT,
    triggered_by    TEXT,
    job_id          TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details         JSONB
);

CREATE TABLE IF NOT EXISTS docker_events (
    id              SERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,
    container_name  TEXT,
    service_name    TEXT,
    image           TEXT,
    host            TEXT NOT NULL,
    exit_code       INTEGER,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details         JSONB
);

CREATE TABLE IF NOT EXISTS incident_markers (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    severity        TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    resolved_at     TIMESTAMPTZ,
    affected_services TEXT[],
    root_cause      TEXT,
    resolution      TEXT,
    timeline_query  TEXT,
    knowledge_pack  JSONB
);

-- ============================================================
-- Updates: What's outdated and how risky is it
-- ============================================================

CREATE TABLE IF NOT EXISTS update_status (
    id              SERIAL PRIMARY KEY,
    service         TEXT NOT NULL,
    deployed        TEXT,
    latest          TEXT,
    status          TEXT NOT NULL,
    last_checked_at TIMESTAMPTZ NOT NULL,
    last_incident_at TIMESTAMPTZ,
    update_risk     TEXT DEFAULT 'unknown',
    details         JSONB
);

-- ============================================================
-- State Snapshots: Point-in-time platform state
-- ============================================================

CREATE TABLE IF NOT EXISTS state_snapshots (
    id              TEXT PRIMARY KEY,
    host            TEXT NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,
    disk_usage_pct  NUMERIC,
    memory_usage_pct NUMERIC,
    docker_services INTEGER,
    docker_containers INTEGER,
    raw_json        JSONB
);

-- ============================================================
-- Indexes for common query patterns
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_actual_services_observed
    ON actual_services (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_actual_services_host
    ON actual_services (host);
CREATE INDEX IF NOT EXISTS idx_drift_observations_unresolved
    ON drift_observations (resolved_at) WHERE resolved_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_drift_observations_upsert
    ON drift_observations (service_name, category) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_drift_observations_severity
    ON drift_observations (severity);
CREATE INDEX IF NOT EXISTS idx_deploy_events_occurred
    ON deploy_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_docker_events_occurred
    ON docker_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_docker_events_type
    ON docker_events (event_type);
CREATE INDEX IF NOT EXISTS idx_update_status_service
    ON update_status (service);
CREATE INDEX IF NOT EXISTS idx_state_snapshots_host
    ON state_snapshots (host, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_markers_started
    ON incident_markers (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_markers_severity
    ON incident_markers (severity);
CREATE INDEX IF NOT EXISTS idx_incident_markers_unresolved
    ON incident_markers (resolved_at) WHERE resolved_at IS NULL;

-- ============================================================
-- Views: Incident Timeline Reconstruction (Phase 5.3)
-- ============================================================

-- Unified event timeline across all event sources.
-- Use this view with time-range filters for incident reconstruction:
--   SELECT * FROM ops_unified_timeline
--   WHERE occurred_at BETWEEN '2025-01-15 03:00' AND '2025-01-15 04:00'
--   ORDER BY occurred_at;
CREATE OR REPLACE VIEW ops_unified_timeline AS
SELECT
    occurred_at,
    'deploy' AS source,
    event_type,
    app_name AS entity,
    environment,
    details
FROM deploy_events
UNION ALL
SELECT
    occurred_at,
    'docker' AS source,
    event_type,
    COALESCE(container_name, service_name) AS entity,
    host AS environment,
    details
FROM docker_events
UNION ALL
SELECT
    started_at AS occurred_at,
    'incident' AS source,
    severity AS event_type,
    title AS entity,
    COALESCE(affected_services[1], 'unknown') AS environment,
    knowledge_pack AS details
FROM incident_markers;
