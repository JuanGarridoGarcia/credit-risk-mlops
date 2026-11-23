-- Step 2.3, D-058: the versions built on a clean load that is no longer the live one of
-- its month and stream (a corrected delivery replaced it, or the month was deleted).
SELECT DISTINCT s.version
FROM ops.training_set_loads AS s
JOIN ops.ingest_log AS used ON used.load_id = s.load_id
JOIN LATERAL (
    SELECT g.load_id, g.status
    FROM ops.ingest_log AS g
    WHERE g.layer = used.layer AND g.stream = used.stream AND g.period = used.period
      AND g.status IN ('loaded', 'replaced', 'deleted')
    ORDER BY g.load_id DESC
    LIMIT 1
) AS live ON true
WHERE live.load_id <> s.load_id OR live.status = 'deleted'
ORDER BY 1;
