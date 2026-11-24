-- Step 4.1, D-107: the simulated clock. Schema "sim" belongs to the simulated world, like
-- the simulator (D-043): system code never reads it (T17.3). Never edited once merged
-- (D-048).

-- migrate:up
CREATE SCHEMA sim;

-- One row: the last simulated month the system completed.
CREATE TABLE sim.clock (
    one        boolean     PRIMARY KEY DEFAULT true CHECK (one),
    month      date        NOT NULL CHECK (month = date_trunc('month', month)),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- migrate:down
DROP TABLE sim.clock;
DROP SCHEMA sim;
