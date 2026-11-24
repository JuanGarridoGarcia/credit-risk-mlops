-- Step 2.3, D-060, D-088: what training may see. Every listing column, the label, the LGD
-- label and the split.
COPY (
    SELECT {columns}, t.label, t.lgd, t.split
    FROM clean.listings AS l
    JOIN pg_temp.training_ids AS t USING (id)
    WHERE t.split IS NOT NULL
    ORDER BY l.id
) TO STDOUT WITH (FORMAT csv, HEADER true)
