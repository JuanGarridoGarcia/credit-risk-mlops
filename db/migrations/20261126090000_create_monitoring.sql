-- Step 6.1, D-138 to D-146: monitoring of the models in service, one table per kind of
-- measure (D-146). Never edited once merged (D-048).

-- migrate:up
CREATE SCHEMA monitoring;

-- The reference of a pair of champions (D-138, D-142): the listings of the 12 months
-- before the pair's cutoff, scored by the pair with the API's own scoring. One row per
-- variable: its bins and the share of the reference in each. Never deleted: the
-- references of earlier champions are their history.
CREATE TABLE monitoring.reference (
    pd_version  text             NOT NULL,
    lgd_version text             NOT NULL,
    subject     text             NOT NULL,
    kind        text             NOT NULL CHECK (kind IN ('numeric', 'categorical', 'prediction')),
    -- The later training cutoff of the two models, and the months taken (cutoff - 12 to
    -- cutoff - 1).
    cutoff      date             NOT NULL CHECK (cutoff = date_trunc('month', cutoff)),
    first_month date             NOT NULL CHECK (first_month = date_trunc('month', first_month)),
    last_month  date             NOT NULL CHECK (last_month = date_trunc('month', last_month)),
    rows        integer          NOT NULL CHECK (rows >= 0),
    nulls       integer          NOT NULL CHECK (nulls BETWEEN 0 AND rows),
    -- Numeric: the cut points (deciles). Categorical: the categories seen.
    edges       double precision[],
    categories  text[],
    -- One share per bin, then (categorical) the "new" bin, then the missing-value bin.
    shares      double precision[] NOT NULL
                CHECK (0 <= ALL (shares) AND 1 >= ALL (shares)),
    minimum     double precision,
    maximum     double precision,
    -- Values drawn from the reference for the KS statistic (numeric only).
    sample      double precision[],
    built_at    timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (pd_version, lgd_version, subject),
    CHECK (first_month < last_month AND last_month < cutoff),
    CHECK ((kind = 'categorical') = (categories IS NOT NULL)),
    CHECK ((kind = 'categorical') = (edges IS NULL)),
    CHECK (minimum IS NULL OR maximum IS NULL OR minimum <= maximum)
);

-- Drift of each variable in each month, for the pair of champions that answered (D-139).
CREATE TABLE monitoring.drift (
    period      date             NOT NULL CHECK (period = date_trunc('month', period)),
    pd_version  text             NOT NULL,
    lgd_version text             NOT NULL,
    subject     text             NOT NULL,
    kind        text             NOT NULL CHECK (kind IN ('numeric', 'categorical', 'prediction')),
    rows        integer          NOT NULL CHECK (rows > 0),
    psi         double precision NOT NULL CHECK (psi >= 0),
    -- For information only (D-139): numeric variables and predictions.
    ks          double precision CHECK (ks BETWEEN 0 AND 1),
    null_share  double precision NOT NULL CHECK (null_share BETWEEN 0 AND 1),
    -- Categories never seen in the reference, or numbers outside its range.
    new_values  integer          NOT NULL CHECK (new_values BETWEEN 0 AND rows),
    computed_at timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (period, pd_version, lgd_version, subject),
    FOREIGN KEY (pd_version, lgd_version, subject)
        REFERENCES monitoring.reference (pd_version, lgd_version, subject)
);

-- The 12-month default rate of a cohort against what its PD expected (D-143), measured
-- in the month ``evaluated`` = cohort + 17 months.
CREATE TABLE monitoring.early_warning (
    cohort            date             NOT NULL CHECK (cohort = date_trunc('month', cohort)),
    term              smallint         NOT NULL CHECK (term IN (36, 60)),
    pd_version        text             NOT NULL,
    evaluated         date             NOT NULL
                      CHECK (evaluated = (cohort + interval '17 months')::date),
    loans             integer          NOT NULL CHECK (loans > 0),
    defaults          integer          NOT NULL CHECK (defaults BETWEEN 0 AND loans),
    expected_defaults double precision NOT NULL CHECK (expected_defaults > 0),
    observed_rate     double precision NOT NULL CHECK (observed_rate BETWEEN 0 AND 1),
    expected_rate     double precision NOT NULL CHECK (expected_rate > 0 AND expected_rate <= 1),
    ratio             double precision NOT NULL CHECK (ratio >= 0),
    ratio_low         double precision NOT NULL,
    ratio_high        double precision NOT NULL,
    -- For information only: the PD's AUC on the 12-month default.
    auc               double precision CHECK (auc BETWEEN 0 AND 1),
    computed_at       timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (cohort, term, pd_version),
    CHECK (0 <= ratio_low AND ratio_low <= ratio AND ratio <= ratio_high)
);

-- The real performance of a matured cohort (term + 5 months, D-144), overall
-- (segment 'all') and by grade ('grade=A'...). The LGD and the purchases only overall.
CREATE TABLE monitoring.performance (
    cohort            date             NOT NULL CHECK (cohort = date_trunc('month', cohort)),
    term              smallint         NOT NULL CHECK (term IN (36, 60)),
    pd_version        text             NOT NULL,
    lgd_version       text             NOT NULL,
    segment           text             NOT NULL CHECK (segment = 'all' OR segment ~ '^grade=.+$'),
    evaluated         date             NOT NULL
                      CHECK (evaluated = (cohort + make_interval(months => term + 5))::date),
    loans             integer          NOT NULL CHECK (loans >= 0),
    defaults          integer          NOT NULL CHECK (defaults BETWEEN 0 AND loans),
    -- Loans with no final outcome yet (or of the old policy): left out, counted.
    unresolved        integer          NOT NULL CHECK (unresolved >= 0),
    auc               double precision CHECK (auc BETWEEN 0 AND 1),
    brier             double precision CHECK (brier BETWEEN 0 AND 1),
    calibration_error double precision CHECK (calibration_error BETWEEN 0 AND 1),
    mean_pd           double precision CHECK (mean_pd BETWEEN 0 AND 1),
    default_rate      double precision CHECK (default_rate BETWEEN 0 AND 1),
    lgd_loans         integer          CHECK (lgd_loans >= 0),
    lgd_rmse          double precision CHECK (lgd_rmse >= 0),
    lgd_level         double precision,
    purchases         integer          CHECK (purchases >= 0),
    invested          double precision CHECK (invested >= 0),
    received          double precision CHECK (received >= 0),
    realised_return   double precision,
    computed_at       timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (cohort, term, pd_version, lgd_version, segment),
    CHECK (segment = 'all' OR (lgd_loans IS NULL AND purchases IS NULL))
);

CREATE INDEX drift_subject ON monitoring.drift (subject, period);
CREATE INDEX early_warning_evaluated ON monitoring.early_warning (evaluated);
CREATE INDEX performance_evaluated ON monitoring.performance (evaluated);

-- migrate:down
DROP SCHEMA monitoring CASCADE;
