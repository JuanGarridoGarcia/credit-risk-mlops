-- R5: rows of the live clean load of each of the 12 months before a period, if any.
SELECT period, rows_loaded
FROM (
    SELECT DISTINCT ON (period) period, status, rows_loaded
    FROM ops.ingest_log
    WHERE stream = %(stream)s
      AND layer = 'clean'
      AND status IN ('loaded', 'replaced', 'deleted')
      AND period >= (%(period)s::date - interval '12 months')
      AND period < %(period)s::date
    ORDER BY period, load_id DESC
) AS live
WHERE status <> 'deleted'
ORDER BY period;
