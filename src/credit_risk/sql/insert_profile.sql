-- R4.6: store the missing values of one column of a month that entered clean.
INSERT INTO ops.column_profile (period, stream, column_name, rows_total, rows_null, load_id)
VALUES (%(period)s, %(stream)s, %(column)s, %(rows)s, %(nulls)s, %(load_id)s);
