-- Step 2.3: the loans of the training set at the cutoff (D-040, D-013, D-042).
-- Matured cohorts: listed at least term + lag months before the cutoff. The label comes
-- only from outcomes delivered by the cutoff. The last 6 listing months of the labelled
-- loans are the validation set.
-- Runs after create_training_ids.sql, inside the same transaction.
INSERT INTO pg_temp.training_ids (id, period, loan_status, resolved_period, label, split)
WITH matured AS (
    SELECT l.id, l.period
    FROM clean.listings AS l
    WHERE l.period <= (%(cutoff)s::date - make_interval(months => l.term + %(lag)s))::date
),
resolved AS (
    SELECT m.id, m.period, o.loan_status, o.period AS resolved_period
    FROM matured AS m
    LEFT JOIN clean.outcomes AS o ON o.id = m.id AND o.period <= %(cutoff)s::date
),
labelled AS (
    SELECT id, period, loan_status, resolved_period,
           CASE
               WHEN loan_status = ANY (%(good)s) THEN 0
               WHEN loan_status = ANY (%(bad)s) THEN 1
           END::smallint AS label
    FROM resolved
),
boundary AS (
    SELECT (max(period) - interval '6 months')::date AS last_train
    FROM labelled
    WHERE label IS NOT NULL
)
SELECT id, period, loan_status, resolved_period, label,
       CASE
           WHEN label IS NULL THEN NULL
           WHEN period > boundary.last_train THEN 'validation'
           ELSE 'train'
       END AS split
FROM labelled
CROSS JOIN boundary;
