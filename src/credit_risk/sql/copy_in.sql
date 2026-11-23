-- Bulk load with COPY (D-047). CSV: an unquoted empty field is NULL.
COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)
