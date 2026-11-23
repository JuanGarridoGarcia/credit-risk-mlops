-- Step 2.3: for every month from the first delivery to the cutoff and every stream, the
-- clean load whose rows are there now (if any) and the status of the last attempt.
SELECT m.period::date AS period, s.stream, live.load_id, live.status, last.status AS last_status
FROM generate_series(%(first)s::date, %(cutoff)s::date, interval '1 month') AS m (period)
CROSS JOIN (VALUES ('listings'), ('outcomes')) AS s (stream)
LEFT JOIN LATERAL (
    SELECT g.load_id, g.status
    FROM {log} AS g
    WHERE g.layer = 'clean' AND g.stream = s.stream AND g.period = m.period
      AND g.status IN ('loaded', 'replaced', 'deleted')
    ORDER BY g.load_id DESC
    LIMIT 1
) AS live ON true
LEFT JOIN LATERAL (
    SELECT g.status
    FROM {log} AS g
    WHERE g.layer = 'clean' AND g.stream = s.stream AND g.period = m.period
      AND g.status <> 'unchanged'
    ORDER BY g.load_id DESC
    LIMIT 1
) AS last ON true
ORDER BY 1, 2;
