-- Step 2.2, D-054 and R4.6: warnings of the months that entered clean, and the profile of
-- missing values of each month and column. Never edited once merged (D-048).

-- migrate:up
CREATE TABLE ops.validation_warnings (
    period        date    NOT NULL CHECK (period = date_trunc('month', period)),
    stream        text    NOT NULL CHECK (stream IN ('listings', 'outcomes')),
    rule          text    NOT NULL CHECK (rule ~ '^R[1-5]\.[0-9]+$'),
    column_name   text,
    rows_affected integer NOT NULL CHECK (rows_affected > 0),
    -- The clean load that the warning belongs to; replaced with the month.
    load_id       bigint  NOT NULL REFERENCES ops.ingest_log (load_id),
    -- Up to 20 examples: [[loan id, value], ...].
    examples      jsonb   NOT NULL DEFAULT '[]'::jsonb
);

CREATE UNIQUE INDEX validation_warnings_key
    ON ops.validation_warnings (period, stream, rule, coalesce(column_name, ''));

CREATE TABLE ops.column_profile (
    period      date    NOT NULL CHECK (period = date_trunc('month', period)),
    stream      text    NOT NULL CHECK (stream IN ('listings', 'outcomes')),
    column_name text    NOT NULL,
    rows_total  integer NOT NULL CHECK (rows_total >= 0),
    rows_null   integer NOT NULL CHECK (rows_null >= 0 AND rows_null <= rows_total),
    load_id     bigint  NOT NULL REFERENCES ops.ingest_log (load_id),
    PRIMARY KEY (period, stream, column_name)
);

-- migrate:down
DROP TABLE ops.column_profile;
DROP TABLE ops.validation_warnings;
