-- Close a load with the number of rows actually written.
UPDATE {log}
SET rows_loaded = %(rows_loaded)s, finished_at = now()
WHERE load_id = %(load_id)s;
