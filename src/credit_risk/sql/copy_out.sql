-- Read one period of a raw table back as CSV, in contract order and numeric id order
-- (length first, so "99" comes before "100" without casting text that may be broken).
COPY (SELECT {columns} FROM {table} WHERE period = {period} ORDER BY length(id), id) TO STDOUT
WITH (FORMAT csv, HEADER true)
