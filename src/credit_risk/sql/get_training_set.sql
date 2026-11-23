-- Step 2.3: the manifest of one version, if it exists.
SELECT version, cutoff, git_commit, path, rows_train, rows_validation, bad_train,
       bad_validation, excluded_old_policy, excluded_unresolved, features_sha256,
       evaluation_sha256
FROM ops.training_sets
WHERE version = %(version)s;
