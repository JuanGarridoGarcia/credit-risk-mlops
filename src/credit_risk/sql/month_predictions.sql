-- Step 6.1, D-141: what the champions received and answered for the loans listed in a
-- month, the first prediction of each loan.
SELECT DISTINCT ON (loan_id) pd_version, lgd_version, features, pd, lgd, el_rate
FROM serving.predictions
WHERE listed = %(period)s
ORDER BY loan_id, prediction_id;
