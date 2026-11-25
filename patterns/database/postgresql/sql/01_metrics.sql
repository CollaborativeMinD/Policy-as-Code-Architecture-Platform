-- PG-SCHEMA-001 / PG-QUERY-001 / PG-CONTRACT-001.
-- Apply as migration owner, never as the application's runtime role.
CREATE SCHEMA IF NOT EXISTS hmt_pg;
REVOKE CREATE ON SCHEMA hmt_pg FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hmt_pg.metrics (
    id bigint PRIMARY KEY CHECK (id > 0),
    status text NOT NULL CHECK (status IN ('active', 'inactive')),
    telemetry jsonb NOT NULL CHECK (jsonb_typeof(telemetry) = 'object'),
    observed_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS metrics_status_id_idx ON hmt_pg.metrics(status, id);
COMMENT ON TABLE hmt_pg.metrics IS 'PG-CONTRACT-001: validated telemetry reference';
