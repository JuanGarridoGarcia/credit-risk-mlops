-- Step 2.1, D-049: one row per load of a period of a stream into a layer.
-- Migrations are never edited once merged into main (D-048).

-- migrate:up
CREATE SCHEMA ops;

CREATE TABLE ops.ingest_log (
    load_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stream         text        NOT NULL CHECK (stream IN ('listings', 'outcomes')),
    layer          text        NOT NULL CHECK (layer IN ('raw', 'clean')),
    period         date        NOT NULL CHECK (period = date_trunc('month', period)),
    status         text        NOT NULL
                   CHECK (status IN ('loaded', 'replaced', 'unchanged', 'failed', 'deleted')),
    -- raw: SHA-256 of the delivery file; clean: that of the raw load it was built from.
    file_sha256    text        CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    source_load_id bigint      REFERENCES ops.ingest_log (load_id),
    rows_in_file   integer     CHECK (rows_in_file >= 0),
    rows_loaded    integer     CHECK (rows_loaded >= 0),
    error          text,
    started_at     timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz,
    CHECK (status <> 'failed' OR error IS NOT NULL),
    CHECK (status NOT IN ('loaded', 'replaced') OR rows_loaded = rows_in_file)
);

CREATE INDEX ingest_log_stream_layer_period ON ops.ingest_log (stream, layer, period);

-- migrate:down
DROP TABLE ops.ingest_log;
DROP SCHEMA ops;
