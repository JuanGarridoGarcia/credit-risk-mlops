-- Step 2.3: the loans of a training set being built; dropped at the end of the build.
CREATE TEMP TABLE training_ids (
    id              bigint   PRIMARY KEY,
    period          date     NOT NULL,
    loan_status     text,
    resolved_period date,
    label           smallint CHECK (label IN (0, 1)),
    lgd             double precision,
    split           text     CHECK (split IN ('train', 'validation'))
) ON COMMIT DROP;
