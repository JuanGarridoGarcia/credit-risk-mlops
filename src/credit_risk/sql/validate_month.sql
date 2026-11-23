-- Step 2.2: the rules that need other months (docs/validation_rules.md, engine S).
-- Runs inside the load transaction, after the month was copied to the stage tables and
-- before it replaces the clean month. One row per failing value:
-- (rule, stream, column_name, loan_id, value). Levels come from the catalogue in Python.
WITH listings AS (
    -- Every listing known after this month: clean history plus the month being loaded.
    SELECT id, period, issue_d, loan_amnt, installment, int_rate, term
    FROM clean.listings
    WHERE period <> %(period)s
    UNION ALL
    SELECT id, period, issue_d, loan_amnt, installment, int_rate, term
    FROM pg_temp.stage_listings
),
outcomes AS (
    SELECT o.*, l.issue_d, l.loan_amnt, l.installment, l.int_rate, l.term,
           l.period AS listing_period
    FROM pg_temp.stage_outcomes AS o
    LEFT JOIN listings AS l USING (id)
)
-- R1.3: a loan is listed once and resolved once.
SELECT 'R1.3' AS rule, 'listings' AS stream, 'id' AS column_name, s.id AS loan_id,
       to_char(c.period, 'YYYY-MM') AS value
FROM pg_temp.stage_listings AS s
JOIN clean.listings AS c USING (id)
WHERE c.period <> %(period)s
UNION ALL
SELECT 'R1.3', 'outcomes', 'id', s.id, to_char(c.period, 'YYYY-MM')
FROM pg_temp.stage_outcomes AS s
JOIN clean.outcomes AS c USING (id)
WHERE c.period <> %(period)s
UNION ALL
-- R1.5: the resolution month computed from the row is the month of the delivery.
SELECT 'R1.5', 'outcomes', 'loan_status', id, coalesce(to_char(expected, 'YYYY-MM'), 'unknown')
FROM (
    SELECT id,
           CASE
               WHEN loan_status = ANY (%(bad)s) THEN
                   least(
                       (coalesce(last_pymnt_d, issue_d)
                        + make_interval(months => %(lag)s))::date,
                       %(snapshot)s::date
                   )
               ELSE last_pymnt_d
           END AS expected
    FROM outcomes
) AS resolved
WHERE expected IS DISTINCT FROM %(period)s::date
UNION ALL
-- R1.6: every outcome has its listing, from the same month or earlier.
SELECT 'R1.6', 'outcomes', 'id', id, coalesce(to_char(listing_period, 'YYYY-MM'), 'missing')
FROM outcomes
WHERE listing_period IS NULL OR listing_period > %(period)s
UNION ALL
-- R3.11: a loan is not funded above the request.
SELECT 'R3.11', 'outcomes', 'funded_amnt', id, funded_amnt::text
FROM outcomes
WHERE funded_amnt > loan_amnt + 0.01
UNION ALL
-- R3.12: no payment before the loan exists.
SELECT 'R3.12', 'outcomes', 'last_pymnt_d', id, to_char(last_pymnt_d, 'YYYY-MM')
FROM outcomes
WHERE last_pymnt_d < issue_d
UNION ALL
-- R2.13 (warning): a rate above the highest rate seen in clean so far.
SELECT 'R2.13', 'listings', 'int_rate', s.id, s.int_rate::text
FROM pg_temp.stage_listings AS s
WHERE s.int_rate > (SELECT max(int_rate) FROM clean.listings WHERE period < %(period)s)
UNION ALL
-- R3.15 (warning): the instalment follows the amortisation formula on the funded amount.
SELECT 'R3.15', 'outcomes', 'installment', id, installment::text
FROM (
    SELECT id, installment,
           funded_amnt * (int_rate / 1200)
           / (1 - power(1 + int_rate / 1200, -term)) AS formula
    FROM outcomes
    WHERE int_rate > 0 AND term > 0 AND funded_amnt > 0
) AS amortised
WHERE abs(installment - formula) > 0.01 * formula
ORDER BY 1, 2, 4;
