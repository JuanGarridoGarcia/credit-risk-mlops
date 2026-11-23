-- R4.6: the missing-value profile of a stream in the month before a period.
SELECT column_name, rows_total, rows_null
FROM ops.column_profile
WHERE stream = %(stream)s
  AND period = (%(period)s::date - interval '1 month')::date;
