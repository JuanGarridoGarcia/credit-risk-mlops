-- Step 4.1, D-108: every event a person should know about, in one table. Grafana reads it
-- in F6 and sends it on. Never edited once merged (D-048).

-- migrate:up
CREATE TABLE ops.alerts (
    alert_id   bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at         timestamptz NOT NULL DEFAULT now(),
    kind       text        NOT NULL
               CHECK (kind IN ('flow_failed', 'promoted', 'rejected', 'rolled_back')),
    severity   text        NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    -- The simulated month the event belongs to, when it has one.
    period     date        CHECK (period = date_trunc('month', period)),
    flow       text,
    task       text,
    model      text,
    version    text,
    previous   text,
    message    text        NOT NULL,
    details    jsonb       NOT NULL DEFAULT '{}'::jsonb
);

-- A verdict on a registered version happens once (D-101): running the month again must
-- not repeat its alert.
CREATE UNIQUE INDEX alerts_verdict_once
    ON ops.alerts (kind, model, version) WHERE kind IN ('promoted', 'rejected');

-- migrate:down
DROP TABLE ops.alerts;
