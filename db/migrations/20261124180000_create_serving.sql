-- Step 5.1, D-113 to D-115: every request to the API and every prediction it served.
-- Never edited once merged (D-048).

-- migrate:up
CREATE SCHEMA serving;

-- One row per request (D-115), whatever its outcome. The body and the errors are kept
-- only for rejected input: a valid request lives on in its predictions.
CREATE TABLE serving.requests (
    request_id  uuid             PRIMARY KEY,
    at          timestamptz      NOT NULL DEFAULT now(),
    endpoint    text             NOT NULL,
    -- The name of the API key used, never the key (D-118); null when none was valid.
    client      text,
    status      smallint         NOT NULL CHECK (status BETWEEN 100 AND 599),
    latency_ms  double precision NOT NULL CHECK (latency_ms >= 0),
    loans       integer          NOT NULL DEFAULT 0 CHECK (loans >= 0),
    rejected    integer          NOT NULL DEFAULT 0 CHECK (rejected >= 0),
    pd_version  text,
    lgd_version text,
    rule_version text,
    api_version text             NOT NULL,
    body        jsonb,
    errors      jsonb
);

CREATE INDEX requests_at ON serving.requests (at);

-- One row per prediction (D-113): what is filtered on in columns, what is audited in
-- jsonb. A loan scored again by the same pair of models is not stored twice (D-114).
CREATE TABLE serving.predictions (
    prediction_id   bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id      uuid             NOT NULL REFERENCES serving.requests (request_id),
    at              timestamptz      NOT NULL DEFAULT now(),
    loan_id         bigint           NOT NULL,
    listed          date             CHECK (listed = date_trunc('month', listed)),
    pd_version      text             NOT NULL,
    lgd_version     text             NOT NULL,
    rule_version    text,
    api_version     text             NOT NULL,
    covered         boolean          NOT NULL,
    pd              double precision CHECK (pd BETWEEN 0 AND 1),
    lgd             double precision CHECK (lgd BETWEEN 0 AND 1),
    ead             double precision,
    expected_loss   double precision,
    el_rate         double precision,
    expected_return double precision,
    minimum         double precision,
    passes          boolean,
    base_value      double precision,
    contributions   jsonb,
    reasons         jsonb            NOT NULL DEFAULT '[]'::jsonb,
    features        jsonb            NOT NULL,
    request         jsonb            NOT NULL,
    -- A covered loan has its whole risk; an uncovered one has none of it (D-070).
    CHECK (covered = (pd IS NOT NULL AND lgd IS NOT NULL AND contributions IS NOT NULL)),
    CONSTRAINT predictions_once UNIQUE (loan_id, pd_version, lgd_version)
);

CREATE INDEX predictions_listed ON serving.predictions (listed);
CREATE INDEX predictions_request ON serving.predictions (request_id);

-- migrate:down
DROP SCHEMA serving CASCADE;
