-- Step 2.3: the loans of the training set at the cutoff (D-040, D-013, D-069, D-088).
-- Matured cohorts: listed at least term + lag months before the cutoff. The label comes
-- only from outcomes delivered by the cutoff. Validation is taken per term (D-069): the
-- last 6 matured listing months of each term (36 months: T-46 to T-41; 60 months: T-70
-- to T-65); earlier matured loans are training. The LGD label (D-088) is filled only for
-- bad loans resolved at least lgd_age months before the cutoff (D-017).
-- Runs after create_training_ids.sql, inside the same transaction.
INSERT INTO pg_temp.training_ids (id, period, loan_status, resolved_period, label, lgd, split)
WITH matured AS (
    SELECT l.id, l.period, l.term
    FROM clean.listings AS l
    WHERE l.period <= (%(cutoff)s::date - make_interval(months => l.term + %(lag)s))::date
),
resolved AS (
    SELECT m.id, m.period, m.term, o.loan_status, o.period AS resolved_period,
           o.funded_amnt, o.total_rec_prncp, o.recoveries, o.collection_recovery_fee
    FROM matured AS m
    LEFT JOIN clean.outcomes AS o ON o.id = m.id AND o.period <= %(cutoff)s::date
),
labelled AS (
    SELECT *,
           CASE
               WHEN loan_status = ANY (%(good)s) THEN 0
               WHEN loan_status = ANY (%(bad)s) THEN 1
           END::smallint AS label
    FROM resolved
)
SELECT id, period, loan_status, resolved_period, label,
       CASE
           WHEN label = 1
            AND resolved_period
                <= (%(cutoff)s::date - make_interval(months => %(lgd_age)s))::date
           THEN (funded_amnt - total_rec_prncp - (recoveries - collection_recovery_fee))
                / NULLIF(funded_amnt, 0)
       END AS lgd,
       CASE
           WHEN label IS NULL THEN NULL
           WHEN period > (%(cutoff)s::date
                          - make_interval(months => term + %(lag)s + %(window)s))::date
           THEN 'validation'
           ELSE 'train'
       END AS split
FROM labelled;
