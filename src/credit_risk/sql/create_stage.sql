-- A private copy of a clean table for the month being validated (step 2.2). It lives
-- only inside the load transaction and is dropped at its end.
CREATE TEMP TABLE {stage} (LIKE {table}) ON COMMIT DROP;
