-- Step 6.1, D-143, D-144: the covered loans of a cohort as the champions first answered
-- them (the first prediction of each loan), with what is known of their outcome at the
-- month %(at)s (outcomes delivered by then) and the dollars bought of each.
WITH first AS (
    SELECT DISTINCT ON (loan_id)
           loan_id, pd_version, lgd_version, covered, pd, lgd,
           (features ->> 'term')::integer AS term, features ->> 'grade' AS grade
    FROM serving.predictions
    WHERE listed = %(cohort)s
    ORDER BY loan_id, prediction_id
)
SELECT f.loan_id, f.pd_version, f.lgd_version, f.term, f.grade, f.pd, f.lgd,
       o.loan_status, o.period AS resolved, o.last_pymnt_d, o.funded_amnt, o.total_pymnt,
       o.total_rec_prncp, o.recoveries, o.collection_recovery_fee,
       coalesce(
           (SELECT sum(p.amount) FROM serving.purchases AS p WHERE p.loan_id = f.loan_id), 0
       )::double precision AS amount
FROM first AS f
LEFT JOIN clean.outcomes AS o ON o.id = f.loan_id AND o.period <= %(at)s::date
WHERE f.covered
ORDER BY f.loan_id;
