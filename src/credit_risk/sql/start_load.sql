-- Open a load: its id is stored in every row it writes.
INSERT INTO {log} (stream, layer, period, status, file_sha256, source_load_id, rows_in_file)
VALUES (%(stream)s, %(layer)s, %(period)s, %(status)s, %(sha)s, %(source)s, %(rows_in_file)s)
RETURNING load_id;
