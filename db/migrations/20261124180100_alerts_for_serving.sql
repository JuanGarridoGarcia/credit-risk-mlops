-- Step 5.1, D-111: two more kinds of alert. A champion the API could not load (it keeps
-- the pair it had), and a reload notice from the flow that did not reach the API.
-- Never edited once merged (D-048).

-- migrate:up
ALTER TABLE ops.alerts DROP CONSTRAINT alerts_kind_check;
ALTER TABLE ops.alerts ADD CONSTRAINT alerts_kind_check CHECK (
    kind IN ('flow_failed', 'promoted', 'rejected', 'rolled_back', 'model_load_failed',
             'reload_failed')
);

-- migrate:down
ALTER TABLE ops.alerts DROP CONSTRAINT alerts_kind_check;
ALTER TABLE ops.alerts ADD CONSTRAINT alerts_kind_check
    CHECK (kind IN ('flow_failed', 'promoted', 'rejected', 'rolled_back'));
