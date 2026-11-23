-- D-054: store a warning of a month that entered clean.
INSERT INTO ops.validation_warnings (period, stream, rule, column_name, rows_affected, load_id, examples)
VALUES (%(period)s, %(stream)s, %(rule)s, %(column)s, %(rows)s, %(load_id)s, %(examples)s);
