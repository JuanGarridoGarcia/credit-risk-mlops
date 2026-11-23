-- The load whose rows are in the table now for a period of a stream and layer, if any:
-- the latest load that wrote or deleted rows ('unchanged' and 'failed' write nothing).
-- Returns no row, or a row with status 'deleted', when the period is empty.
SELECT load_id, file_sha256, source_load_id, status
FROM {log}
WHERE stream = %(stream)s
  AND layer = %(layer)s
  AND period = %(period)s
  AND status IN ('loaded', 'replaced', 'deleted')
ORDER BY load_id DESC
LIMIT 1;
