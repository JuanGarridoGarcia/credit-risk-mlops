-- Step 2.3: what the training set holds and what it left out, for the manifest.
SELECT count(*) FILTER (WHERE split = 'train') AS rows_train,
       count(*) FILTER (WHERE split = 'validation') AS rows_validation,
       count(*) FILTER (WHERE split = 'train' AND label = 1) AS bad_train,
       count(*) FILTER (WHERE split = 'validation' AND label = 1) AS bad_validation,
       count(*) FILTER (WHERE loan_status = ANY (%(old_policy)s)) AS excluded_old_policy,
       count(*) FILTER (WHERE loan_status IS NULL) AS excluded_unresolved,
       count(*) FILTER (
           WHERE loan_status IS NOT NULL AND label IS NULL
             AND NOT loan_status = ANY (%(old_policy)s)
       ) AS unknown_status
FROM pg_temp.training_ids;
