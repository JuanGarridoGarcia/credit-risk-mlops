-- Step 6.1, D-143: the defaults of the cohorts matured at the cutoff (D-040), by term and
-- grade, and how many of them stopped paying within 12 months of issue (first missed
-- payment, the month after the last payment, no later than issue + 12 months; data_audit.md
-- 4.2). Only outcomes delivered by the cutoff count.
SELECT l.term::integer, l.grade, count(*)::integer AS defaults,
       count(*) FILTER (
           WHERE o.last_pymnt_d IS NULL
              OR date_trunc('month', o.last_pymnt_d)
                 <= l.period + make_interval(months => %(early)s - 1)
       )::integer AS early
FROM clean.listings AS l
JOIN clean.outcomes AS o ON o.id = l.id AND o.period <= %(cutoff)s::date
WHERE l.period <= (%(cutoff)s::date - make_interval(months => l.term + %(lag)s))::date
  AND o.loan_status = ANY (%(bad)s)
GROUP BY l.term, l.grade
ORDER BY l.term, l.grade;
