-- Step 2.3, D-058 to D-061: the manifest of every training set version.
-- Never edited once merged (D-048).

-- migrate:up
CREATE TABLE ops.training_sets (
    -- Content hash (D-061): the identity of the version and its folder in the store.
    version             text        PRIMARY KEY CHECK (version ~ '^[0-9a-f]{64}$'),
    cutoff              date        NOT NULL CHECK (cutoff = date_trunc('month', cutoff)),
    git_commit          text        NOT NULL,
    path                text        NOT NULL,
    rows_train          integer     NOT NULL CHECK (rows_train >= 0),
    rows_validation     integer     NOT NULL CHECK (rows_validation >= 0),
    bad_train           integer     NOT NULL CHECK (bad_train BETWEEN 0 AND rows_train),
    bad_validation      integer     NOT NULL CHECK (bad_validation BETWEEN 0 AND rows_validation),
    -- Matured loans left out: old credit policy (D-013), outcome not known by the cutoff.
    excluded_old_policy integer     NOT NULL CHECK (excluded_old_policy >= 0),
    excluded_unresolved integer     NOT NULL CHECK (excluded_unresolved >= 0),
    -- File checksums (D-061), verified every time a file is read.
    features_sha256     text        NOT NULL CHECK (features_sha256 ~ '^[0-9a-f]{64}$'),
    evaluation_sha256   text        NOT NULL CHECK (evaluation_sha256 ~ '^[0-9a-f]{64}$'),
    built_at            timestamptz NOT NULL DEFAULT now()
);

-- The clean load of every month and stream the version was built from (D-058).
CREATE TABLE ops.training_set_loads (
    version text   NOT NULL REFERENCES ops.training_sets (version),
    load_id bigint NOT NULL REFERENCES ops.ingest_log (load_id),
    PRIMARY KEY (version, load_id)
);

-- migrate:down
DROP TABLE ops.training_set_loads;
DROP TABLE ops.training_sets;
