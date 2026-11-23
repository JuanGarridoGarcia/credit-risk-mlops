-- Step 2.3, D-058: the manifest of a new version.
INSERT INTO ops.training_sets (
    version, cutoff, git_commit, path, rows_train, rows_validation, bad_train,
    bad_validation, excluded_old_policy, excluded_unresolved, features_sha256,
    evaluation_sha256
) VALUES (
    %(version)s, %(cutoff)s, %(git_commit)s, %(path)s, %(rows_train)s, %(rows_validation)s,
    %(bad_train)s, %(bad_validation)s, %(excluded_old_policy)s, %(excluded_unresolved)s,
    %(features_sha256)s, %(evaluation_sha256)s
);
