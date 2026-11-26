-- Step 6.2, D-155: the role Grafana reads with, and nothing more than the tables its
-- dashboards read. It cannot write anything, nor read raw, clean or the features of
-- serving.predictions. Its login and password are set apart, from the environment
-- (credit_risk.monitoring.grafana), so no password is in a migration. A role belongs to
-- the whole server: created only if missing. Never edited once merged (D-048).

-- migrate:up
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana_reader') THEN
        CREATE ROLE grafana_reader NOLOGIN;
    END IF;
END
$$;
GRANT USAGE ON SCHEMA monitoring, ops, serving TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA monitoring TO grafana_reader;
GRANT SELECT ON ops.alerts, ops.task_runs, ops.training_sets TO grafana_reader;
GRANT SELECT ON serving.requests TO grafana_reader;
-- A long or runaway query of a dashboard never holds the database.
ALTER ROLE grafana_reader SET statement_timeout = '30s';
ALTER ROLE grafana_reader SET default_transaction_read_only = on;

-- migrate:down
REVOKE ALL ON serving.requests FROM grafana_reader;
REVOKE ALL ON ops.alerts, ops.task_runs, ops.training_sets FROM grafana_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA monitoring FROM grafana_reader;
REVOKE USAGE ON SCHEMA monitoring, ops, serving FROM grafana_reader;
