-- F5, second pull request, D-123: the months the simulated investor has already sent to
-- the API and bought from. Schema "sim" belongs to the simulated world (D-043): system
-- code never reads it (T17.3). Never edited once merged (D-048).

-- migrate:up
-- One row per month the replayer completed. A month repeated by the clock after a later
-- failure (the system's flow) is not sent again: the investor already acted on it.
CREATE TABLE sim.invested (
    month    date        PRIMARY KEY CHECK (month = date_trunc('month', month)),
    at       timestamptz NOT NULL DEFAULT now(),
    listings integer     NOT NULL CHECK (listings >= 0),
    scored   integer     NOT NULL CHECK (scored >= 0),
    refused  integer     NOT NULL CHECK (refused >= 0),
    k        integer     NOT NULL CHECK (k >= 0),
    bought   integer     NOT NULL CHECK (bought >= 0 AND bought <= k)
);

-- migrate:down
DROP TABLE sim.invested;
