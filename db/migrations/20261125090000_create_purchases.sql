-- F5, second pull request, D-124 to D-129: what the investor reports it bought. Never
-- edited once merged (D-048).

-- migrate:up
-- One row per order (D-129). The client's own order number makes a repeat harmless: the
-- same order twice is one row. A new order on the same loan adds to the client's share
-- (a repurchase); the API keeps a client's share within the loan's amount.
CREATE TABLE serving.purchases (
    purchase_id   bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id    uuid          NOT NULL REFERENCES serving.requests (request_id),
    at            timestamptz   NOT NULL DEFAULT now(),
    -- The name of the API key used, never the key (D-118).
    client        text          NOT NULL,
    order_id      text          NOT NULL CHECK (length(order_id) BETWEEN 1 AND 100),
    -- The answer the purchase was decided on (D-126), and so the models behind it.
    prediction_id bigint        NOT NULL REFERENCES serving.predictions (prediction_id),
    loan_id       bigint        NOT NULL,
    -- Dollars, in notes of 25 (D-128).
    amount        numeric(12, 2) NOT NULL CHECK (amount > 0 AND amount % 25 = 0),
    -- Where the purchase stands against the buy rule of its answer: exceptions are
    -- recorded, not refused (D-126).
    policy        text          NOT NULL
        CHECK (policy IN ('passes', 'below_minimum', 'no_threshold', 'not_covered')),
    CONSTRAINT purchases_once UNIQUE (client, order_id)
);

CREATE INDEX purchases_loan ON serving.purchases (client, loan_id);
CREATE INDEX purchases_prediction ON serving.purchases (prediction_id);

-- migrate:down
DROP TABLE serving.purchases;
