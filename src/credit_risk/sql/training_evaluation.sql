-- Step 2.3, D-060: what only evaluation may see. The outcome of every loan of the set,
-- with the month it was resolved (for the LGD rule of D-017).
COPY (
    SELECT {columns}, t.resolved_period
    FROM clean.outcomes AS o
    JOIN pg_temp.training_ids AS t USING (id)
    WHERE t.split IS NOT NULL
    ORDER BY o.id
) TO STDOUT WITH (FORMAT csv, HEADER true)
