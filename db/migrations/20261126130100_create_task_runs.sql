-- Step 6.2, D-154: every attempt of every task of the monthly flow, for the dashboard of
-- the system: the month, the task, when it started, how long it took and how it ended.
-- Written by the flow itself (credit_risk.flows.recorded), not read from Prefect's own
-- tables. Never edited once merged (D-048).

-- migrate:up
CREATE TABLE ops.task_runs (
    task_run_id bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    period      date             NOT NULL CHECK (period = date_trunc('month', period)),
    flow        text             NOT NULL,
    task        text             NOT NULL,
    flow_run    text,
    -- 1 for the first attempt, 2 for the first retry (D-102)...
    attempt     integer          NOT NULL CHECK (attempt >= 1),
    started     timestamptz      NOT NULL,
    seconds     double precision NOT NULL CHECK (seconds >= 0),
    state       text             NOT NULL CHECK (state IN ('completed', 'failed')),
    error       text,
    CHECK ((state = 'failed') = (error IS NOT NULL))
);
CREATE INDEX task_runs_period ON ops.task_runs (period, task);
CREATE INDEX task_runs_started ON ops.task_runs (started);

-- migrate:down
DROP TABLE ops.task_runs;
