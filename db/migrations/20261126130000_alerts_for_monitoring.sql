-- Step 6.2, D-149, D-151: four more kinds of alert, what the monitoring of a month and a
-- new LGD found; and the intervals of the real performance of a whole cohort, which the
-- rule of a performance drop reads (D-156). Never edited once merged (D-048).

-- migrate:up
ALTER TABLE ops.alerts DROP CONSTRAINT alerts_kind_check;
ALTER TABLE ops.alerts ADD CONSTRAINT alerts_kind_check CHECK (
    kind IN ('flow_failed', 'promoted', 'rejected', 'rolled_back', 'model_load_failed',
             'reload_failed', 'prediction_drift', 'early_warning', 'performance_drop',
             'lgd_level_shift')
);
-- A monitoring signal of a month is recorded once, however many times the month runs
-- (D-145); the signal names what was measured and on which models.
ALTER TABLE ops.alerts ADD CONSTRAINT alerts_signal_named CHECK (
    kind NOT IN ('prediction_drift', 'early_warning', 'performance_drop')
    OR (period IS NOT NULL AND details ? 'signal')
);
CREATE UNIQUE INDEX alerts_signal_once
    ON ops.alerts (kind, period, (details ->> 'signal'))
    WHERE kind IN ('prediction_drift', 'early_warning', 'performance_drop');
-- A level correction belongs to a registered version: once (D-101).
CREATE UNIQUE INDEX alerts_level_once
    ON ops.alerts (kind, model, version) WHERE kind = 'lgd_level_shift';
-- Grafana asks for the recent warnings and errors every minute (D-147).
CREATE INDEX alerts_at ON ops.alerts (at);

ALTER TABLE monitoring.performance
    ADD COLUMN auc_low          double precision CHECK (auc_low BETWEEN 0 AND 1),
    ADD COLUMN auc_high         double precision CHECK (auc_high BETWEEN 0 AND 1),
    ADD COLUMN calibration_low  double precision CHECK (calibration_low BETWEEN 0 AND 1),
    ADD COLUMN calibration_high double precision CHECK (calibration_high BETWEEN 0 AND 1),
    ADD CONSTRAINT performance_auc_interval CHECK (auc_low <= auc AND auc <= auc_high),
    ADD CONSTRAINT performance_calibration_interval
        CHECK (calibration_low <= calibration_error AND calibration_error <= calibration_high),
    ADD CONSTRAINT performance_intervals_whole_cohort
        CHECK (segment = 'all' OR (auc_low IS NULL AND calibration_low IS NULL));

-- migrate:down
ALTER TABLE monitoring.performance
    DROP CONSTRAINT performance_intervals_whole_cohort,
    DROP CONSTRAINT performance_calibration_interval,
    DROP CONSTRAINT performance_auc_interval,
    DROP COLUMN calibration_high,
    DROP COLUMN calibration_low,
    DROP COLUMN auc_high,
    DROP COLUMN auc_low;
DROP INDEX ops.alerts_at;
DROP INDEX ops.alerts_level_once;
DROP INDEX ops.alerts_signal_once;
ALTER TABLE ops.alerts DROP CONSTRAINT alerts_signal_named;
DELETE FROM ops.alerts
WHERE kind IN ('prediction_drift', 'early_warning', 'performance_drop', 'lgd_level_shift');
ALTER TABLE ops.alerts DROP CONSTRAINT alerts_kind_check;
ALTER TABLE ops.alerts ADD CONSTRAINT alerts_kind_check CHECK (
    kind IN ('flow_failed', 'promoted', 'rejected', 'rolled_back', 'model_load_failed',
             'reload_failed')
);
