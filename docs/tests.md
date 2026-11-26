# Test catalogue

Every test of the project, what it checks, where it lives and where it runs. Juan approves each test before it is written ([README](../README.md)); this file is the record of what he approved and of every later change. Test B6 keeps it in step with the code.

## Contents

- [How tests are organised](#how-tests-are-organised)
- [How a test is added or changed](#how-a-test-is-added-or-changed)
- [Summary](#summary)
- [B Foundations](#b-foundations)
- [T1 Simulator](#t1-simulator)
- [T2 Cleaning](#t2-cleaning)
- [T3 Loading](#t3-loading)
- [T4 Validation](#t4-validation)
- [T5 Training set versions](#t5-training-set-versions)
- [T6 Features](#t6-features)
- [T7 Training](#t7-training)
- [T8 Tracking](#t8-tracking)
- [T9 Model comparison](#t9-model-comparison)
- [T10 Behaviour](#t10-behaviour)
- [T11 Registry](#t11-registry)
- [T12 LGD](#t12-lgd)
- [T13 Explanations](#t13-explanations)
- [T14 Model card](#t14-model-card)
- [T15 Buy rule and business metric](#t15-buy-rule-and-business-metric)
- [T16 Orchestration](#t16-orchestration)
- [T17 Clock and alerts](#t17-clock-and-alerts)
- [T18 API](#t18-api)
- [T19 Buy rule in the flow](#t19-buy-rule-in-the-flow)
- [T20 Purchases](#t20-purchases)
- [T21 Simulated investor](#t21-simulated-investor)
- [T22 Delivery](#t22-delivery)
- [T23 Drift](#t23-drift)
- [T24 Monitoring reference](#t24-monitoring-reference)
- [T25 Early warning](#t25-early-warning)
- [T26 Real performance](#t26-real-performance)
- [T27 Monitoring in the flow](#t27-monitoring-in-the-flow)
- [T28 Monitoring on the real data](#t28-monitoring-on-the-real-data)
- [Change history](#change-history)

## How tests are organised

Tests are grouped by the piece they check. Group B holds the foundations (package, settings, Postgres, images); groups T1 to T6 belong to the steps of F2 and T7 to T15 to the model of F3. Every test has an ID; a test can be one or more pytest functions.

| Kind | Folder | pytest marker | Needs | Command | Runs in |
|---|---|---|---|---|---|
| Unit | `tests/unit/` | none | Nothing | `make test`, `make test-image` | CI (job `tests`), and inside the image (job `integration`) |
| Integration | `tests/integration/` | `integration` (`destructive` for B4 and T8.2) | Docker: compose Postgres and MLflow, or the built images | `make test-integration` | CI (job `integration`) |
| Data | `tests/data/` | `data` | The real Lending Club file and its deliveries in `data/` (and Postgres for T3.13, T3.15, T4.15, T5.13, T5.14, T6.8, T10.6, T12.6, T14.6, T15.7, T17.9, T18.15, T28.1, T28.2; MLflow for T14.6, T17.9 and T28.2; the Prefect server for T17.9 and T28.2) | `make test-data` | Local only: the file is 1.6 GB and Kaggle needs a token |

Integration and data tests never skip: if what they need is missing, they fail.

## How a test is added or changed

1. Propose the test (what it checks and why) and wait for Juan's approval.
2. Write it with a comment `# <ID>` on the line just before its first function (for example `# T3.4`). The functions that follow belong to that ID until the next marker.
3. Add its row to this catalogue with every function as `file::function`.
4. Add a line to the [change history](#change-history): date, ID, change and why.

Changing what an approved test checks needs Juan's approval again. B6 fails if a marker has no row here, a row has no marker, a marker sits in a file its row does not name, a row names a function that does not exist, or a test function in `tests/` is in no row.

## Summary

| Group | Phase and step | Tests | Approved by Juan | Where they are described |
|---|---|---|---|---|
| B Foundations | F1, steps 1.1 and 1.2; F3 (B5 changed, B7, B8); F4 (B7 changed) | 8 | 2026-11-22 (B1 to B5), 2026-11-23 (B6), 2026-11-24 (B5 changed, B7, B8; B7 changed in F4) | [technical.md, F1](technical.md#3-f1-foundations) |
| T1 Simulator | F2, step 2.1 | 12 | 2026-11-23 | [technical.md, step 2.1](technical.md#step-21-idempotent-ingestion) |
| T2 Cleaning | F2, step 2.1 | 11 | 2026-11-23 | [technical.md, step 2.1](technical.md#step-21-idempotent-ingestion) |
| T3 Loading | F2, step 2.1 | 15 | 2026-11-23 (T3.14 and T3.15 on approval in step 2.2) | [technical.md, step 2.1](technical.md#step-21-idempotent-ingestion) |
| T4 Validation | F2, step 2.2 | 16 | 2026-11-23 | [validation_rules.md](validation_rules.md), [technical.md, step 2.2](technical.md#step-22-data-validation) |
| T5 Training set versions | F2, step 2.3; F3 (D-069, D-088) | 15 | 2026-11-23; 2026-11-24 (T5.4, T5.5, T5.12, T5.13 changed, T5.15 added) | [technical.md, step 2.3](technical.md#step-23-data-versioning) |
| T6 Features | F2, step 2.4 | 8 | 2026-11-23 | [technical.md, step 2.4](technical.md#step-24-features) |
| T7 Training | F3, second pull request | 5 | 2026-11-24 | [technical.md, F3](technical.md#second-pull-request-training) |
| T8 Tracking | F3, second pull request | 4 | 2026-11-24 | [technical.md, F3](technical.md#second-pull-request-training) |
| T9 Model comparison | F3, second pull request | 4 | 2026-11-24 (T9.3 margin case added the same day) | [technical.md, F3](technical.md#second-pull-request-training) |
| T10 Behaviour | F3, second pull request | 6 | 2026-11-24 (T10.4 changed in the third pull request) | [technical.md, F3](technical.md#second-pull-request-training) |
| T11 Registry | F3, second pull request | 5 | 2026-11-24 | [technical.md, F3](technical.md#second-pull-request-training) |
| T12 LGD | F3, second pull request | 7 | 2026-11-24 (T12.6 changed and T12.7 added the same day, D-094) | [technical.md, F3](technical.md#second-pull-request-training) |
| T13 Explanations | F3, third pull request | 5 | 2026-11-24 | [technical.md, F3](technical.md#third-pull-request-explanations-and-business) |
| T14 Model card | F3, third pull request | 6 | 2026-11-24 | [technical.md, F3](technical.md#third-pull-request-explanations-and-business) |
| T15 Buy rule and business metric | F3, third pull request | 7 | 2026-11-24 | [technical.md, F3](technical.md#third-pull-request-explanations-and-business) |
| T16 Orchestration | F4, step 4.1, first pull request | 10 | 2026-11-24 | [technical.md, F4](technical.md#6-f4-automation) |
| T17 Clock and alerts | F4, step 4.1, second pull request | 9 | 2026-11-24 | [technical.md, F4](technical.md#second-pull-request-the-simulated-clock-cadence-and-alerts) |
| T18 API | F5, step 5.1, first pull request | 15 | 2026-11-24 (T18.13 changed the same day, D-122) | [technical.md, F5](technical.md#first-pull-request-the-api-and-the-predictions-table) |
| T19 Buy rule in the flow | F5, step 5.1, first pull request | 2 | 2026-11-24 | [technical.md, F5](technical.md#first-pull-request-the-api-and-the-predictions-table) |
| T20 Purchases | F5, old step 4.2, second pull request | 5 | 2026-11-25 | [technical.md, F5](technical.md#second-pull-request-the-simulated-investor-and-its-purchases) |
| T21 Simulated investor | F5, old step 4.2, second pull request | 5 | 2026-11-25 | [technical.md, F5](technical.md#second-pull-request-the-simulated-investor-and-its-purchases) |
| T22 Delivery | F5, step 5.2, third pull request | 6 | 2026-11-25 (T22.1 and T22.4 extended, T22.5 added, the same day; T22.6 added after E-056) | [technical.md, F5](technical.md#third-pull-request-versioned-images-in-a-registry) |
| T23 Drift | F6, step 6.1, first pull request | 6 | 2026-11-26 | [technical.md, F6](technical.md#first-pull-request-drift-and-metrics) |
| T24 Monitoring reference | F6, step 6.1, first pull request | 3 | 2026-11-26 | [technical.md, F6](technical.md#first-pull-request-drift-and-metrics) |
| T25 Early warning | F6, step 6.1, first pull request | 4 | 2026-11-26 | [technical.md, F6](technical.md#first-pull-request-drift-and-metrics) |
| T26 Real performance | F6, step 6.1, first pull request | 2 | 2026-11-26 | [technical.md, F6](technical.md#first-pull-request-drift-and-metrics) |
| T27 Monitoring in the flow | F6, step 6.1, first pull request | 5 | 2026-11-26 | [technical.md, F6](technical.md#first-pull-request-drift-and-metrics) |
| T28 Monitoring on the real data | F6, step 6.1, first pull request | 2 | 2026-11-26 | [technical.md, F6](technical.md#first-pull-request-drift-and-metrics) |
| **Total** | | **208** | | |

## B Foundations

F1, steps 1.1 and 1.2; B7 and B8 come with the two images of F3 (D-078).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| B1 | The package imports and its version is read from `pyproject.toml`, its only source | `tests/unit/test_version.py::test_package_version_matches_pyproject` | Unit | CI, image |
| B2 | Settings come from the environment; a missing variable fails with its name; the password never appears in `str()`, `repr()` or JSON | `tests/unit/test_settings.py::test_settings_read_from_env`<br>`tests/unit/test_settings.py::test_settings_missing_variable_fails_clearly`<br>`tests/unit/test_settings.py::test_settings_never_expose_password` | Unit | CI, image |
| B3 | Our settings connect to the compose Postgres and `SELECT 1` returns 1; the server's major version is 18 | `tests/integration/test_postgres.py::test_postgres_accepts_connection`<br>`tests/integration/test_postgres.py::test_postgres_major_version_is_18` | Integration | CI |
| B4 | A random value in a table with a random name survives `docker compose down` + `up` (a new container); the table is dropped afterwards. Marked `destructive`: runs last and alone | `tests/integration/test_persistence.py::test_postgres_data_survives_container_recreation` | Integration | CI |
| B5 | Each image (`serve`, `train`) runs as non-root, has no `.env*` file, no secret in its configuration or build history, prints the right version, and stays within its budget: `serve` 800 MB, `train` 1.5 GB, measured as the sum of its layers (D-078, E-028) | `tests/integration/test_image.py::test_image_runs_as_non_root`<br>`tests/integration/test_image.py::test_image_has_no_env_file`<br>`tests/integration/test_image.py::test_image_has_no_secrets_in_config`<br>`tests/integration/test_image.py::test_image_default_command_works`<br>`tests/integration/test_image.py::test_image_size_within_budget` | Integration | CI |
| B6 | Every test marker in `tests/` is in this catalogue and the other way round, in the same file; every function named here exists; every test function in `tests/` is named here | `tests/unit/test_catalogue.py::test_markers_and_catalogue_agree` | Unit | CI, image |
| B7 | `serve` carries nothing of training: importing Optuna, SHAP, the full MLflow server or Prefect fails inside it | `tests/integration/test_image.py::test_serve_carries_nothing_of_training` | Integration | CI |
| B8 | A small model trained in `train`, saved and loaded in `serve` gives identical predictions | `tests/integration/test_image.py::test_a_model_trained_in_train_predicts_the_same_in_serve` | Integration | CI |

## T1 Simulator

F2, step 2.1.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T1.1 | A source file with the wrong hash is rejected | `tests/unit/simulator/test_simulator.py::test_source_with_wrong_hash_is_rejected` | Unit | CI, image |
| T1.2 | Each loan is listed once, in its issue month | `tests/unit/simulator/test_simulator.py::test_each_loan_is_listed_once_in_its_issue_month` | Unit | CI, image |
| T1.3 | Listing deliveries hold exactly the dictionary's listing columns, none of the outcome | `tests/unit/simulator/test_simulator.py::test_listings_hold_exactly_the_listing_columns`<br>`tests/unit/simulator/test_simulator.py::test_listing_delivery_has_the_contract_columns` | Unit | CI, image |
| T1.4 | Outcome deliveries hold `id` and only outcome columns | `tests/unit/simulator/test_simulator.py::test_outcome_delivery_has_id_and_only_outcome_columns` | Unit | CI, image |
| T1.5 | Resolution month by hand: paid, bad, never paid, capped at the snapshot, Default, old policy | `tests/unit/simulator/test_simulator.py::test_resolution_month` | Unit | CI, image |
| T1.6 | Running loans produce no outcome; an unknown status stops the simulator | `tests/unit/simulator/test_simulator.py::test_running_loans_produce_no_outcome`<br>`tests/unit/simulator/test_simulator.py::test_unknown_status_stops_the_simulator` | Unit | CI, image |
| T1.7 | Text arrives unchanged | `tests/unit/simulator/test_simulator.py::test_text_arrives_unchanged` | Unit | CI, image |
| T1.8 | Publishing twice gives identical bytes; the gzip header has no timestamp | `tests/unit/simulator/test_simulator.py::test_publishing_twice_gives_identical_bytes`<br>`tests/unit/simulator/test_simulator.py::test_gzip_header_has_no_timestamp` | Unit | CI, image |
| T1.9 | Summary rows are dropped wherever they are, no loan is lost, the count is reported; any other odd row stops it | `tests/unit/simulator/test_simulator.py::test_summary_rows_are_dropped_wherever_they_are`<br>`tests/unit/simulator/test_simulator.py::test_a_row_that_is_not_a_loan_nor_a_summary_stops_the_simulator` | Unit | CI, image |
| T1.10 | No outcome arrives before its listing; nothing after the simulated date is published | `tests/unit/simulator/test_simulator.py::test_no_outcome_arrives_before_its_listing`<br>`tests/unit/simulator/test_simulator.py::test_nothing_after_the_simulated_date_is_published` | Unit | CI, image |
| T1.11 | System code never imports the simulator or names the source file | `tests/unit/simulator/test_simulator.py::test_system_code_never_touches_the_simulator` | Unit | CI, image |
| T1.12 | Real file: 2,260,668 listings, 1,348,099 outcomes, 33 summary rows, snapshot 2019-03; no outcome before its listing | `tests/data/test_simulator_data.py::test_counts_match_the_audit`<br>`tests/data/test_simulator_data.py::test_no_outcome_before_its_listing_on_the_real_file` | Data | Local |

## T2 Cleaning

F2, step 2.1.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T2.1 | Numbers: values that fit and values that must fail | `tests/unit/test_cleaning.py::test_number` | Unit | CI, image |
| T2.2 | Months (`Mar-2015`): values that fit and values that must fail | `tests/unit/test_cleaning.py::test_month` | Unit | CI, image |
| T2.3 | `term`: values that fit and values that must fail | `tests/unit/test_cleaning.py::test_term` | Unit | CI, image |
| T2.4 | `emp_length`: values that fit and values that must fail | `tests/unit/test_cleaning.py::test_emp_length` | Unit | CI, image |
| T2.5 | Flags: values that fit and values that must fail | `tests/unit/test_cleaning.py::test_flag` | Unit | CI, image |
| T2.6 | Text is unchanged | `tests/unit/test_cleaning.py::test_text_is_unchanged` | Unit | CI, image |
| T2.7 | Every contract column has exactly one rule; a frame with other columns is refused | `tests/unit/test_cleaning.py::test_every_contract_column_has_exactly_one_rule`<br>`tests/unit/test_cleaning.py::test_a_frame_with_other_columns_is_refused` | Unit | CI, image |
| T2.8 | The error names the column, the loan and the value | `tests/unit/test_cleaning.py::test_error_names_column_loan_and_value` | Unit | CI, image |
| T2.9 | Rows and their order are kept | `tests/unit/test_cleaning.py::test_rows_and_order_are_kept` | Unit | CI, image |
| T2.10 | One row at a time gives the same result as a whole month (D-045) | `tests/unit/test_cleaning.py::test_one_row_or_a_month_give_the_same_result` | Unit | CI, image |
| T2.11 | The 284 real deliveries clean with no error and the same missing values per column | `tests/data/test_cleaning_data.py::test_real_deliveries_clean_with_the_same_missing_values` | Data | Local |

## T3 Loading

F2, step 2.1.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T3.1 | Migrations go up, down and up again on an empty database | `tests/integration/test_ingest.py::test_migrations_apply_roll_back_and_apply_again` | Integration | CI |
| T3.2 | A load writes every row and logs it | `tests/integration/test_ingest.py::test_a_load_writes_every_row_and_logs_it` | Integration | CI |
| T3.3 | The same file twice changes nothing | `tests/integration/test_ingest.py::test_the_same_file_twice_changes_nothing` | Integration | CI |
| T3.4 | A corrected delivery replaces the month with no ghost row | `tests/integration/test_ingest.py::test_a_corrected_delivery_replaces_the_month_with_no_ghost` | Integration | CI |
| T3.5 | A failure (truncated record; primary key violation during `COPY`) leaves the month as it was and is logged | `tests/integration/test_ingest.py::test_a_failed_load_leaves_the_month_as_it_was`<br>`tests/integration/test_ingest.py::test_a_failure_inside_postgres_rolls_back_the_delete` | Integration | CI |
| T3.6 | Deleting a month leaves the others | `tests/integration/test_ingest.py::test_deleting_a_month_leaves_the_others` | Integration | CI |
| T3.7 | Text survives Postgres | `tests/integration/test_ingest.py::test_text_survives_postgres` | Integration | CI |
| T3.8 | SQL injection is stored as text | `tests/integration/test_ingest.py::test_sql_injection_is_stored_as_text` | Integration | CI |
| T3.9 | Clean holds exactly the cleaned delivery, with Postgres types | `tests/integration/test_ingest.py::test_clean_holds_exactly_the_cleaned_delivery_with_postgres_types` | Integration | CI |
| T3.10 | Clean is rebuilt from raw without the delivery file | `tests/integration/test_ingest.py::test_clean_is_rebuilt_from_raw_without_the_delivery` | Integration | CI |
| T3.11 | A missing delivery names the expected file | `tests/integration/test_ingest.py::test_a_missing_delivery_names_the_expected_file` | Integration | CI |
| T3.12 | A loan in two months is rejected by the primary key | `tests/integration/test_ingest.py::test_a_loan_in_two_months_is_rejected_by_the_primary_key` | Integration | CI |
| T3.13 | Real data: all 142 months load with the audit counts | `tests/data/test_ingest_data.py::test_every_delivery_loads_with_the_audit_counts` | Data | Local |
| T3.14 | Ingestion refuses a connection without autocommit, so that a failure record is never rolled back with the failed load | `tests/integration/test_ingest.py::test_ingestion_refuses_a_connection_without_autocommit` | Integration | CI |
| T3.15 | Real data: `COPY` is faster than row-by-row `INSERT` on 10,000 rows of the largest month, as D-047 promised (times recorded in technical.md, step 2.1) | `tests/data/test_ingest_data.py::test_copy_is_faster_than_row_by_row_insert` | Data | Local |

## T4 Validation

F2, step 2.2.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T4.1 | A valid month passes every rule | `tests/unit/test_validation.py::test_a_valid_month_passes_every_rule` | Unit | CI, image |
| T4.2 | Each critical pandera rule fails on a valid row with one change and names itself, the loan and the value (36 cases); every rule has a case | `tests/unit/test_validation.py::test_each_critical_rule_names_itself_the_loan_and_the_value`<br>`tests/unit/test_validation.py::test_every_critical_pandera_rule_has_a_case` | Unit | CI, image |
| T4.3 | Each warning lets the month pass and is counted (7 cases); every warning has a case | `tests/unit/test_validation.py::test_each_warning_rule_reports_and_lets_the_month_pass`<br>`tests/unit/test_validation.py::test_every_warning_pandera_rule_has_a_case` | Unit | CI, image |
| T4.4 | Three broken rules are reported at once | `tests/unit/test_validation.py::test_all_failures_of_a_month_are_reported_at_once` | Unit | CI, image |
| T4.5 | Limits are inclusive: amount, rate, money tolerance, FICO, `dti`, volume ratios and the 1,000 minimum, 12 months of history, missing share 10 points | `tests/unit/test_validation.py::test_critical_limits_are_inclusive`<br>`tests/unit/test_validation.py::test_warning_limits_are_inclusive`<br>`tests/unit/test_validation.py::test_volume_limits`<br>`tests/unit/test_validation.py::test_volume_needs_twelve_months_of_history`<br>`tests/unit/test_validation.py::test_missing_share_limit_is_ten_points` | Unit | CI, image |
| T4.6 | Each dated change fails the month before and passes from its month (C1 to C9); listings must be empty once the source ends (C8) | `tests/unit/test_validation.py::test_a_value_fails_the_month_before_its_change_and_passes_from_it`<br>`tests/unit/test_validation.py::test_listings_must_be_empty_once_the_source_ends` | Unit | CI, image |
| T4.7 | A reviewed exception passes only its rule, loan and month | `tests/unit/test_validation.py::test_a_reviewed_exception_passes_only_its_rule_loan_and_month` | Unit | CI, image |
| T4.8 | Cleaning reports every failing column at once | `tests/unit/test_validation.py::test_cleaning_reports_every_failing_column_at_once` | Unit | CI, image |
| T4.9 | Every rule in the code is in `docs/validation_rules.md` and the other way round | `tests/unit/test_validation.py::test_every_rule_in_the_code_is_in_the_catalogue_and_the_other_way_round` | Unit | CI, image |
| T4.10 | Each SQL and history rule has a failing case in Postgres (R1.3, R1.5, R1.6, R3.11, R3.12, R2.13, R3.15, R4.6, R5.1 to R5.3) | `tests/integration/test_validation.py::test_r1_3_a_loan_already_in_another_month`<br>`tests/integration/test_validation.py::test_r1_5_an_outcome_in_the_wrong_month`<br>`tests/integration/test_validation.py::test_r1_6_an_outcome_without_its_listing`<br>`tests/integration/test_validation.py::test_r3_11_funded_above_the_request`<br>`tests/integration/test_validation.py::test_r3_12_a_payment_before_the_loan`<br>`tests/integration/test_validation.py::test_r2_13_a_rate_above_every_rate_seen`<br>`tests/integration/test_validation.py::test_r3_15_an_instalment_off_the_formula`<br>`tests/integration/test_validation.py::test_r4_6_a_jump_in_missing_values`<br>`tests/integration/test_validation.py::test_r5_1_a_month_far_below_its_median`<br>`tests/integration/test_validation.py::test_r5_2_a_month_well_below_its_median`<br>`tests/integration/test_validation.py::test_r5_3_no_volume_rule_below_a_median_of_1000` | Integration | CI |
| T4.11 | A critical failure stops the whole month: clean keeps the previous load, a new month leaves nothing, a failing SQL rule rolls back | `tests/integration/test_validation.py::test_a_critical_failure_stops_the_whole_month`<br>`tests/integration/test_validation.py::test_a_new_month_that_fails_leaves_nothing_in_clean`<br>`tests/integration/test_validation.py::test_a_failing_sql_rule_rolls_back_the_month` | Integration | CI |
| T4.12 | Warnings are stored once per month | `tests/integration/test_validation.py::test_warnings_are_stored_once_per_month` | Integration | CI |
| T4.13 | A month that failed enters once fixed | `tests/integration/test_validation.py::test_a_month_that_failed_enters_once_fixed` | Integration | CI |
| T4.14 | Every run writes its JSON report and its summary | `tests/integration/test_validation.py::test_every_run_writes_its_report` | Integration | CI |
| T4.15 | Real data: no critical failure, the 5 reviewed exceptions, and every warning count and month of the catalogue | `tests/data/test_ingest_data.py::test_the_real_file_passes_and_warns_where_the_catalogue_says` | Data | Local |
| T4.16 | Real data: the base contract alone stops exactly at the months of C1 to C9 | `tests/data/test_validation_data.py::test_the_base_contract_alone_stops_exactly_at_the_recorded_changes` | Data | Local |

## T5 Training set versions

F2, step 2.3.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T5.1 | A loan enters once term + 5 months have passed: 36 months at 41 yes and 40 no; 60 months at 65 yes and 64 no (D-040). Since D-069 a training loan is added so the set has both splits | `tests/integration/test_snapshot.py::test_a_loan_enters_once_term_plus_five_months_have_passed` | Integration | CI |
| T5.2 | Label: Fully Paid 0; Charged Off and Default 1; both old-policy statuses left out and counted (D-013) | `tests/integration/test_snapshot.py::test_the_label_follows_d013_and_leaves_the_old_policy_out` | Integration | CI |
| T5.3 | A matured loan whose outcome is not known at T (delivered later, or not yet) is left out and counted; no outcome after T is ever used | `tests/integration/test_snapshot.py::test_an_outcome_unknown_at_t_leaves_the_loan_out` | Integration | CI |
| T5.4 | Validation is taken per term (D-069): 36-month loans listed T-46 to T-41 and 60-month loans listed T-70 to T-65; earlier matured loans are train. Edges: 36 months at T-46 validation and T-47 train; 60 months at T-70 validation and T-71 train. No loan in both | `tests/integration/test_snapshot.py::test_validation_is_the_last_six_matured_months_of_each_term` | Integration | CI |
| T5.5 | `features.parquet` holds exactly the listing columns, the label, the LGD label `lgd` (D-088) and the split, and no outcome column; `evaluation.parquet` holds the outcome columns of the same loans (D-060) | `tests/integration/test_snapshot.py::test_training_sees_no_outcome_column` | Integration | CI |
| T5.6 | The build refuses when a month up to T is missing from clean or its last load failed, and names the month | `tests/integration/test_snapshot.py::test_a_month_missing_from_clean_stops_the_build` | Integration | CI |
| T5.7 | The manifest records T, commit, counts, content hash, file checksums and the live clean load of every month and stream used (D-058) | `tests/integration/test_snapshot.py::test_the_manifest_records_where_the_version_came_from` | Integration | CI |
| T5.8 | The same data in another row order or compression give the same content hash and other bytes; one changed value, type or name changes it (D-061) | `tests/unit/test_snapshot.py::test_content_hash_follows_the_data_not_the_file`<br>`tests/unit/test_snapshot.py::test_one_changed_value_changes_the_content_hash` | Unit | CI, image |
| T5.9 | A rebuild with no change in clean gives the same version and writes nothing | `tests/integration/test_snapshot.py::test_a_rebuild_with_no_change_writes_nothing` | Integration | CI |
| T5.10 | After a corrected month: a new version, the old one untouched, and the query of stale versions finds the old one | `tests/integration/test_snapshot.py::test_a_corrected_month_gives_a_new_version_and_flags_the_old` | Integration | CI |
| T5.11 | A stored file that changed is refused by its checksum, on read and on rebuild | `tests/integration/test_snapshot.py::test_a_stored_file_that_changed_is_refused` | Integration | CI |
| T5.12 | The SQL build equals the rule written again in polars, on 2,000 random loans with every case, including the window per term (D-069, both terms in validation) and `lgd` (D-088, with amounts that give an LGD with no EAD) | `tests/integration/test_snapshot.py::test_the_sql_build_matches_an_independent_polars_version` | Integration | CI |
| T5.13 | Real data at T0 = 2014-01: the counts known at T0 (train 7,733 with 1,019 defaults, validation 4,324 with 429), reconciled with the audit: the 21 and 4 loans resolved after T0, found in the later deliveries, give back 12,078 and 2,230 (E-022). Since F3: unchanged under the split per term (no 60-month loan matured at T0, D-069); 1,336 loans with `lgd` (992 train, 344 validation, D-088) | `tests/data/test_snapshot_data.py::test_the_first_training_set_has_the_audit_counts` | Data | Local |
| T5.14 | Real data at T0: matured loans with no outcome known at T are measured and recorded in the manifest | `tests/data/test_snapshot_data.py::test_loans_without_a_known_outcome_are_measured` | Data | Local |
| T5.15 | The LGD label (D-088): `(funded - principal repaid - (recoveries - collection fee)) / funded` on a hand-made case; filled only for bad loans resolved at least 12 months before T (12 yes, 11 empty, D-017); empty for good loans; a value outside [0, 1] kept as computed | `tests/integration/test_snapshot.py::test_the_lgd_label_follows_d017_and_d088` | Integration | CI |

## T6 Features

F2, step 2.4.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T6.1 | Credit history in months by hand: same month, one month, years apart, across a year end, missing date | `tests/unit/test_features.py::test_credit_history_in_months` | Unit | CI, image |
| T6.2 | FICO midpoint by hand: 4-point and 5-point ranges, missing bound | `tests/unit/test_features.py::test_fico_midpoint` | Unit | CI, image |
| T6.3 | The output is `id` and the 30 features (D-063), in a fixed order, with their types | `tests/unit/test_features.py::test_the_output_is_id_and_the_30_features_with_their_types` | Unit | CI, image |
| T6.4 | No forbidden column reaches the output even when present in the input: outcomes, label, split, `installment`, free text, state, zip code, identifiers, `pub_rec_bankruptcies` | `tests/unit/test_features.py::test_no_forbidden_column_reaches_the_output` | Unit | CI, image |
| T6.5 | Every source column is visible at listing (D-014) and reported since 2007 (D-016), according to the audit's data dictionary | `tests/unit/test_features.py::test_every_source_is_visible_at_listing_and_filled_since_2007` | Unit | CI, image |
| T6.6 | One listing alone gives the same features as inside a whole month, in any order (training equals serving, D-045) | `tests/unit/test_features.py::test_one_row_gives_the_same_as_a_whole_month_in_any_order` | Unit | CI, image |
| T6.7 | The fixed layer fills no gap: each feature is missing exactly where one of its sources is (D-062) | `tests/unit/test_features.py::test_missing_values_stay_missing` | Unit | CI, image |
| T6.8 | Real data: the features of the version at 2018-12 (522,904 loans) compute with no error and every value is within its range | `tests/data/test_features_data.py::test_the_features_of_the_largest_version_are_in_range` | Data | Local |

## T7 Training

F3, second pull request (D-062, D-070, D-073, D-074).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T7.1 | Learned preparation sees training only (D-062): the fill value of `dti` and the known categories of `purpose` equal what is computed by hand on training; extreme values in validation change nothing | `tests/unit/test_model.py::test_learned_preparation_sees_training_only` | Unit | CI, image |
| T7.2 | An odd row does not break prediction: an unseen category, every field empty and extreme values give a finite probability between 0 and 1, for both candidates | `tests/unit/test_model.py::test_an_odd_row_still_gets_a_probability` | Unit | CI, image |
| T7.3 | The inner split for tuning (D-073) is the last 6 matured months of each term inside training, edges tested as in T5.4; the search never receives a validation id (every id used to fit or score a trial is recorded and checked) | `tests/unit/test_train.py::test_the_inner_split_is_the_last_six_training_months_of_each_term`<br>`tests/unit/test_train.py::test_the_search_never_sees_a_validation_loan` | Unit | CI, image |
| T7.4 | Same seed, same result (D-074): two trainings give the same hyperparameters and predictions; the budget is counted, 50 trials for LightGBM and 20 values of `C` for the logistic regression | `tests/unit/test_train.py::test_the_same_seed_gives_the_same_model` | Unit | CI, image |
| T7.5 | Coverage rule (D-070): 200 defaults in training and 200 in validation is covered; 199 in either is not; a loan of an uncovered term gets "not covered", never a PD | `tests/unit/test_model.py::test_a_term_needs_200_defaults_in_training_and_in_validation`<br>`tests/unit/test_model.py::test_an_uncovered_term_gets_no_pd` | Unit | CI, image |

## T8 Tracking

F3, second pull request (D-079). T8.2 recreates the MLflow container and is marked `destructive`, like B4.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T8.1 | The MLflow server starts in compose and answers; its metadata are in the `mlflow` database of our Postgres, not in a file inside the container | `tests/integration/test_tracking.py::test_the_server_answers_and_keeps_its_metadata_in_postgres` | Integration | CI |
| T8.2 | A run with a small artefact survives recreating the MLflow container. Marked `destructive`, like B4 | `tests/integration/test_persistence.py::test_mlflow_runs_and_artefacts_survive_container_recreation` | Integration | CI |
| T8.3 | No run without its required fields: one function logs every run and refuses, naming the field, if the commit, snapshot hash, seed, library versions or metrics with intervals are missing (one case per field); a small real training read back from the server carries all of them | `tests/integration/test_tracking.py::test_every_run_of_a_real_training_carries_the_required_fields`<br>`tests/unit/test_tracking.py::test_a_complete_record_passes`<br>`tests/unit/test_tracking.py::test_a_missing_field_is_refused_by_name`<br>`tests/unit/test_tracking.py::test_log_run_checks_before_writing_anything` | Unit and integration | CI, image |
| T8.4 | The model is rebuilt from what a run records (snapshot version, seed, hyperparameters) and gives the same predictions as the stored model | `tests/integration/test_tracking.py::test_the_model_is_rebuilt_from_what_its_run_recorded` | Integration | CI |

## T9 Model comparison

F3, second pull request (D-068, D-075, D-080, D-081, D-093).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T9.1 | The paired bootstrap (D-075) on cases with a known answer: a clearly better model wins, an identical one does not (difference zero in every resample), a clearly worse one loses; every resample keeps the number of defaults; same seed, same interval; the sign is reversed for a metric where lower is better (Brier) | `tests/unit/test_compare.py::test_a_clearly_better_model_wins_and_a_worse_one_loses`<br>`tests/unit/test_compare.py::test_identical_models_never_win`<br>`tests/unit/test_compare.py::test_every_resample_keeps_the_number_of_defaults`<br>`tests/unit/test_compare.py::test_the_same_seed_gives_the_same_interval`<br>`tests/unit/test_compare.py::test_lower_is_better_for_the_brier_score` | Unit | CI, image |
| T9.2 | The choice rule (D-068): LightGBM is chosen only if its interval against the logistic regression lies entirely above zero; if it touches zero the logistic regression wins, even with a higher mean AUC | `tests/unit/test_compare.py::test_lightgbm_needs_its_interval_above_zero_to_be_chosen` | Unit | CI, image |
| T9.3 | The segments (D-081): F and G merged, covered terms only, quarters of validation; a segment with 49 defaults is merged with its neighbour and one with 50 is not; a model better overall but clearly worse in grade A fails; a tie in a segment passes; clearly worse but within the margin of D-093 passes (case added 2026-11-24, approved by Juan) | `tests/unit/test_compare.py::test_segments_merge_f_and_g_and_small_groups`<br>`tests/unit/test_compare.py::test_a_model_clearly_worse_in_one_segment_fails`<br>`tests/unit/test_compare.py::test_clearly_worse_within_the_margin_passes` | Unit | CI, image |
| T9.4 | The signs (D-080): the nine coefficients of the logistic regression have the expected sign, and made-up data where a higher `int_rate` lowers risk make the check fail; LightGBM is trained with exactly the fixed list of constraints, logged in the run | `tests/unit/test_model.py::test_the_logistic_regression_keeps_the_signs_of_d080`<br>`tests/unit/test_model.py::test_lightgbm_is_trained_with_exactly_the_fixed_constraints` | Unit | CI, image |

## T10 Behaviour

F3, second pull request. The battery (D-086) is a function run on every model before promotion (D-082); these tests check that it does its job.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T10.1 | Invariance: changing fields the model does not use (`id`, `emp_title`, `addr_state`) leaves the PD unchanged; a loan scored alone or in a batch gets exactly the same PD | `tests/unit/test_battery.py::test_unused_fields_and_batch_size_do_not_move_the_pd` | Unit | CI, image |
| T10.2 | Direction: on real validation loans, raising each of the nine features of D-080 in its risk direction never lowers the PD, and the reverse for the protective ones | `tests/unit/test_battery.py::test_raising_a_risk_feature_never_lowers_the_pd` | Unit | CI, image |
| T10.3 | Minimum cases: a clearly good profile (grade A, FICO 800, `dti` 5, no delinquencies) gets a lower PD than a clearly bad one; every PD is between 0 and 1; empty optional fields are scored without error; an uncovered term gets no PD | `tests/unit/test_battery.py::test_the_minimum_cases` | Unit | CI, image |
| T10.4 | Time: one prediction with its explanation (D-083) takes under 50 ms (p95) in process | `tests/unit/test_battery.py::test_one_prediction_takes_under_50_ms` | Unit | CI, image |
| T10.5 | Bad models fail: a constant model and a random model fail the battery | `tests/unit/test_battery.py::test_a_constant_and_a_random_model_fail` | Unit | CI, image |
| T10.6 | Data test: the model trained at T0 on the real data passes the whole battery | `tests/data/test_training_data.py::test_the_model_trained_at_t0_passes_the_battery` | Data | Local |

## T11 Registry

F3, second pull request (D-082, D-090). Integration tests against the MLflow of compose.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T11.1 | Only a challenger that passes every rule is promoted: the alias `champion` moves to it; one case per rule where only that rule fails (noise, a segment, a sign, the battery) leaves the alias where it was; the promotion function has no option to skip a rule | `tests/integration/test_registry.py::test_a_challenger_failing_one_rule_is_not_promoted`<br>`tests/integration/test_registry.py::test_a_challenger_passing_every_rule_is_promoted`<br>`tests/integration/test_registry.py::test_promotion_cannot_skip_a_rule` | Integration | CI |
| T11.2 | Every decision leaves evidence in the challenger's run, promoted or not: intervals, segments, battery results and, if rejected, the reason. Small values as tags and metrics (Postgres), the 1,000 differences, segment table and battery report as artefacts | `tests/integration/test_registry.py::test_every_decision_leaves_evidence` | Integration | CI |
| T11.3 | Every promotion alerts: until Grafana (F6), a WARNING log message with the previous and new champion, plus a tag in MLflow | `tests/integration/test_registry.py::test_every_promotion_alerts` | Integration | CI |
| T11.4 | Rollback in one command (`make rollback MODEL=pd`): the alias returns to the previous champion, read from the tag written on each promoted version; predictions are again exactly those of that model; the rollback leaves evidence and alerts; with no previous champion it fails clearly and changes nothing | `tests/integration/test_registry.py::test_rollback_returns_to_the_previous_champion` | Integration | CI |
| T11.5 | The first champion (D-090): with no champion, the chosen model is compared with the grade-only baseline under the same rules; if it does not beat it, the baseline is the champion | `tests/integration/test_registry.py::test_the_first_champion_must_beat_the_baseline`<br>`tests/integration/test_registry.py::test_a_first_model_that_beats_the_baseline_is_champion` | Integration | CI |

## T12 LGD

F3, second pull request (D-087, D-088, D-094).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T12.1 | Only defaults with a known LGD enter: training and validation use only the rows with `lgd` of their split; good loans, unresolved loans and charge-offs younger than 12 months never enter (ids recorded, as in T7.3) | `tests/unit/test_lgd.py::test_only_defaults_with_a_known_lgd_enter` | Unit | CI, image |
| T12.2 | The baseline: the mean by grade equals the one computed by hand on training and is applied as it is to validation | `tests/unit/test_lgd.py::test_the_baseline_is_the_mean_lgd_by_grade` | Unit | CI, image |
| T12.3 | The baseline can win: with made-up data where LGD is pure noise no candidate beats the mean by grade on RMSE with the paired bootstrap, and the baseline is the champion; with data where LGD clearly depends on a feature, the candidate wins | `tests/unit/test_lgd.py::test_the_baseline_wins_on_noise_and_loses_to_a_real_signal` | Unit | CI, image |
| T12.4 | The level by segment rules: a candidate with a good RMSE but a clearly wrong mean LGD in one grade fails the segment rule of D-081 | `tests/unit/test_lgd.py::test_a_wrong_level_in_one_grade_fails_the_segment_rule` | Unit | CI, image |
| T12.5 | Always between 0 and 1: extreme inputs give a prediction in [0, 1] (the label can fall outside, as the -0.6 of T5.15, and the linear regression extrapolates) | `tests/unit/test_lgd.py::test_lgd_predictions_stay_between_0_and_1` | Unit | CI, image |
| T12.6 | Data test at T0: trained on the 992 training rows, level corrected (D-094) and validated on the 344; logs the RMSE with intervals, the interval against the baseline, the champion, the level shift of each model and the gap before the correction; fixes no winner; the champion's mean predicted LGD in validation is within 0.005 of the observed mean, and no shift exceeds 0.10 | `tests/data/test_training_data.py::test_the_lgd_at_t0_is_on_the_level_of_the_observed_lgd` | Data | Local |
| T12.7 | The level correction of D-094 on made-up data whose validation LGD is 0.10 above training: the shift equals the observed mean minus the mean predicted, by hand; only validation sets it; the order of predictions is unchanged; every prediction stays in [0, 1]; every model, the baseline included, gets its own shift | `tests/unit/test_lgd.py::test_the_level_is_corrected_on_validation_only` | Unit | CI, image |

## T13 Explanations

F3, third pull request (D-083).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T13.1 | Additivity for the logistic regression, LightGBM and the baseline: base value plus contributions equals the log-odds of the calibrated PD (relative and absolute tolerance 1e-9), on validation loans and odd rows (every optional field empty, an unseen category, extreme values) | `tests/unit/test_explain.py::test_base_plus_contributions_is_the_prediction` | Unit | CI, image |
| T13.2 | They are real SHAP values: our contributions equal those of the `shap` library (`LinearExplainer` with the training rows as background, `TreeExplainer`) within 1e-6. Runs where `shap` is installed (CI, the test and train images), never in `serve` | `tests/unit/test_explain.py::test_the_contributions_are_shap_values` | Unit | CI, image |
| T13.3 | One contribution per original feature: one-hot columns and "was missing" columns are summed into their feature; the vector has exactly the 30 features; a feature the model does not use contributes 0 (the baseline: everything but the grade) | `tests/unit/test_explain.py::test_one_contribution_per_original_feature` | Unit | CI, image |
| T13.4 | The four main reasons are the four largest contributions in absolute value, with their sign and the feature's value; ties keep the order of the features; a case by hand. A loan with no PD gets no reasons, and a feature with no contribution is no reason | `tests/unit/test_explain.py::test_the_four_main_reasons_by_hand` | Unit | CI, image |
| T13.5 | The reasons make sense: for the clearly bad profile of the battery the main reason raises the PD, for the clearly good one it lowers it, for both candidates | `tests/unit/test_explain.py::test_the_reasons_make_sense` | Unit | CI, image |

## T14 Model card

F3, third pull request (D-095).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T14.1 | Every registered version has its `model_card.md` in the artefacts of its run, champion or not (the chosen model and the baseline of each target), with every section in order | `tests/integration/test_tracking.py::test_every_registered_version_has_its_model_card` | Integration | CI |
| T14.2 | A card missing any of its sections is refused, naming the section | `tests/unit/test_card.py::test_a_card_without_a_section_is_refused_by_name` | Unit | CI, image |
| T14.3 | The numbers of the card are those of the run: metrics with intervals, training set version, run, and the counts of loans and defaults, which also match a count by hand | `tests/integration/test_tracking.py::test_the_numbers_of_the_card_are_those_of_the_run` | Integration | CI |
| T14.4 | The global importance is the mean absolute contribution on validation, by hand on a small case (covered terms only), largest first | `tests/unit/test_card.py::test_the_importance_is_the_mean_absolute_contribution_by_hand` | Unit | CI, image |
| T14.5 | Each card carries what is particular to its model: the features removed by D-092 for the PD, the level shift of D-094 for the LGD | `tests/integration/test_tracking.py::test_the_card_carries_what_is_particular_to_each_model` | Integration | CI |
| T14.6 | Data test: the cards in `docs/model_cards/` are those of the T0 champions, generated by the same function (title, run and commit aside) | `tests/data/test_training_data.py::test_the_cards_in_docs_are_those_of_the_t0_champions` | Data | Local |

## T15 Buy rule and business metric

F3, third pull request (D-084, D-085, D-096, D-007).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T15.1 | Scheduled interest with the amortisation formula, by hand: 36 months at 7% gives 0.111 and at 20% gives 0.338 (the examples of D-084); a rate of 0% gives 0 | `tests/unit/test_business.py::test_scheduled_interest_by_hand` | Unit | CI, image |
| T15.2 | Expected return = (1 - PD) x scheduled interest - PD x LGD, by hand on the two examples of D-084 (0.083 and 0.103); a loan with no PD (term not covered) is never bought | `tests/unit/test_business.py::test_expected_return_by_hand_and_no_pd_is_never_bought` | Unit | CI, image |
| T15.3 | Budget (D-085): K is 10% of the loans listed the month before, rounded down; loans that pass are bought in listing order until K and the rest are skipped; one 25 dollar note per loan | `tests/unit/test_business.py::test_the_monthly_cap_and_the_listing_order` | Unit | CI, image |
| T15.4 | Realised return by hand: a paid loan, a defaulted one with recoveries and collection fee, and idle money counted as zero; return = (received - invested) / budget | `tests/unit/test_business.py::test_realised_return_by_hand` | Unit | CI, image |
| T15.5 | The minimum is chosen on validation only, from a fixed grid, as the one with the highest realised return under the same budget (a tie goes to the smallest); the ids used are recorded | `tests/unit/test_business.py::test_the_minimum_is_chosen_on_validation_only` | Unit | CI, image |
| T15.6 | On made-up data where our PD is informative and the baseline's is not, our investor earns more with exactly the same budget every month | `tests/unit/test_business.py::test_an_informative_pd_earns_more_with_the_same_budget` | Unit | CI, image |
| T15.7 | Data test (D-096): the T0 champions against the baseline on the loans listed from 2014-02 to 2015-01, with their final outcomes; records realised default rate, loss and net return at caps of 5%, 10% and 20%; fixes no winner; checks the same budget, that everything bought is covered and listed in that year, and that nothing of that year chose the minimum | `tests/data/test_business_data.py::test_the_t0_models_against_the_baseline_on_the_next_year` | Data | Local |

## T16 Orchestration

F4, step 4.1, first pull request (D-099 to D-105). Unit tests use a local SQLite MLflow store; integration tests run the flow against the services of docker compose on a small made-up source (`tests/synthetic_source.py`).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T16.1 | Which failures are retried (D-102): a lost connection to Postgres (`psycopg.OperationalError`) and an MLflow request with no answer, a timeout or a 5xx answer are; `ValidationFailed`, `DeliveryError`, `StoreError`, `SnapshotError`, `RegistryError`, other MLflow errors, a database constraint and an unknown exception are not | `tests/unit/test_flows.py::test_transient_errors_are_retried`<br>`tests/unit/test_flows.py::test_permanent_and_unknown_errors_are_not_retried` | Unit | CI, image |
| T16.2 | Retries are 3, after 10, 30 and 90 seconds; a task that fails twice with a transient error succeeds on the third attempt; a task with a permanent error fails after one attempt (waits set to 0 in the test) | `tests/unit/test_flows.py::test_retries_three_times_on_transient_errors_only` | Unit | CI, image |
| T16.3 | Idempotency key (D-101): training again with the same model, training set and commit reuses the registered version without calling the training; another commit or another training set trains again | `tests/unit/test_flows.py::test_the_same_key_twice_reuses_the_registered_version` | Unit | CI, image |
| T16.4 | A training that logged its runs but never registered its model is not done: the next attempt trains again, and the runs left behind are marked `FAILED` and `orphan` | `tests/unit/test_flows.py::test_a_run_never_registered_is_trained_again_and_marked_failed` | Unit | CI, image |
| T16.5 | Promoting the same version twice returns the stored verdict: no new judgement, no change of champion, tags or metrics, nothing added to the rollback chain; a promotion that stopped after deciding is carried out without judging again | `tests/unit/test_flows.py::test_promoting_the_same_version_twice_changes_nothing` | Unit | CI, image |
| T16.6 | With the PD and the LGD as separate steps (D-100), the LGD receives the covered terms of the PD, and the registered models predict exactly what the training procedure gives on the same data and seed | `tests/unit/test_flows.py::test_the_lgd_gets_the_terms_of_the_pd_and_the_same_models` | Unit | CI, image |
| T16.7 | The whole cycle on small data (the simulator publishes, then the flow loads, versions, trains the PD and the LGD) ends `Completed` with 56 months loaded, the 36-month term covered, one training set and a champion of each model | `tests/integration/test_flows.py::test_the_whole_flow_on_small_data_leaves_two_champions` | Integration | CI |
| T16.8 | A critical validation failure stops the flow: the load task fails in a single attempt with `ValidationFailed`; versioning, PD and LGD never run; the flow is `Failed`; nothing new reaches clean, the training sets or the registry (raw keeps the delivery, by design, D-044) | `tests/integration/test_flows.py::test_a_critical_validation_failure_stops_the_flow` | Integration | CI |
| T16.9 | Running the flow again for the same month ends `Completed` with nothing duplicated: same rows in raw and clean, same training sets, same MLflow runs and registered versions, same champions; PD and LGD report `reused` | `tests/integration/test_flows.py::test_running_the_same_month_again_duplicates_nothing` | Integration | CI |
| T16.10 | The Prefect server of compose answers, keeps its metadata in the database `prefect` of our Postgres, and runs (with its worker) from the `train` image; the deployment `monthly/monthly` is on the server and a run sent through it is executed by the worker (with no deliveries at the given folder, it fails in the load task after one attempt) | `tests/integration/test_flows.py::test_the_prefect_server_runs_the_deployed_flow` | Integration | CI |

## T17 Clock and alerts

F4, step 4.1, second pull request (D-106 to D-108). Unit tests need no Docker (T17.2 runs on a temporary Prefect server); integration tests run the clock against the services of docker compose on the small made-up source, from 2012-01 to 2012-06, with one broken delivery of 2012-03.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T17.1 | Retraining cadence (D-106): `quarterly`, the default, retrains in January, April, July and October and in no other month; `monthly` every month, `yearly` in January; an unknown cadence is refused with a clear message | `tests/unit/test_clock.py::test_the_cadence_retrains_in_its_months_only` | Unit | CI, image |
| T17.2 | When the monthly flow fails, its `on_failure` hook records one `flow_failed` alert (severity error) with the flow, the month, the failed task, the error and the flow run (the writer is replaced by a list in the test) | `tests/unit/test_clock.py::test_a_failed_flow_records_one_alert_with_its_month_task_and_error` | Unit | CI, image |
| T17.3 | The system never touches the clock (D-043, D-107): no module or query of the package outside `simulator/` mentions the schema `sim` | `tests/unit/test_clock.py::test_system_code_never_touches_the_clock_schema` | Unit | CI, image |
| T17.4 | `advance` from an empty clock publishes the history up to the first month, runs the system's flow and records the month; each later `advance` publishes, loads and records the next month only; nothing is published beyond the clock and no month is skipped | `tests/integration/test_clock.py::test_advance_moves_one_month_at_a_time_from_an_empty_clock` | Integration | CI |
| T17.5 | An `advance` whose month has a critical validation failure fails and leaves the clock on the month before; with the delivery corrected, the next `advance` runs that same month and completes it; the broken rows never reach clean | `tests/integration/test_clock.py::test_a_failed_advance_leaves_the_clock_and_the_next_one_repeats_the_month` | Integration | CI |
| T17.6 | Only the cadence months retrain: February and March run the `load` task only; January and April run `load`, `version`, `train-pd` and `train-lgd`, with a new training set in April | `tests/integration/test_clock.py::test_only_the_cadence_months_retrain` | Integration | CI |
| T17.7 | `ops.alerts` (D-108): the failed month leaves exactly one `flow_failed` alert naming the `load` task and the error; every challenger rejected in MLflow has one `rejected` alert with the same reasons, and no other has one; each model's first champion has a `promoted` alert with no previous champion, and the last `promoted` names the current champion; running April again adds no alert; a rollback through `registry.rollback` records one `rolled_back` alert (on a toy model) | `tests/integration/test_clock.py::test_every_event_is_in_the_alerts_table_once` | Integration | CI |
| T17.8 | The `advance` deployment is on the server with its 10-minute schedule paused, and `replay` is deployed with no schedule; `replay` (the flow `make replay` runs) advances month by month until the month asked and returns the months it ran | `tests/integration/test_clock.py::test_the_clock_is_deployed_paused_and_replay_loops_months` | Integration | CI |
| T17.9 | A real year: from an empty clock, `replay` lives 2014-01 to 2014-12 on the real file with the real number of trials: 12 months, 4 training sets, one challenger of each model per quarter with its verdict carried out in MLflow and, when rejected, its alert in `ops.alerts`; no flow fails. It fixes no winner: it prints the verdicts | `tests/data/test_clock_data.py::test_a_real_year_runs_twelve_months_and_retrains_four_times` | Data | Local |

## T18 API

F5, step 5.1, first pull request (D-109 to D-122). Unit tests run the application in process with `TestClient`, made-up champions (`tests/api_support.py`), a registry in memory and an in-memory store; integration tests use the services of docker compose: champions registered in the MLflow server and a migrated database of their own. T18.13 starts the API in a process of its own.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T18.1 | `/predict` with a valid listing: 200 with PD, LGD, expected loss in dollars and as a rate, expected return, whether it passes the threshold, the four main reasons and the versions (PD, LGD, buy rule, API); the values equal scoring in process with the same functions | `tests/unit/test_api.py::test_one_listing_gets_its_full_answer` | Unit | CI, image |
| T18.2 | An uncovered term (D-070): `covered` false, no PD, LGD, loss or threshold, the note "not covered"; it is stored all the same | `tests/unit/test_api.py::test_an_uncovered_term_gets_no_risk_and_is_stored` | Unit | CI, image |
| T18.3 | Invalid input (a required field missing, a broken format, a number that is not text, an unknown field, no id): 422 with the column and the reason; one row in `serving.requests` with the body and the errors; none in `serving.predictions` | `tests/unit/test_api.py::test_invalid_input_is_refused_with_its_column_and_recorded` | Unit | CI, image |
| T18.4 | A batch answers exactly as the loans one by one, in the same order; valid and invalid loans mixed give a result per loan (D-117); more loans than the limit (1,000; lowered in the test), an empty list, loans that are not a list, a wrong key or broken JSON give 422 for the whole batch | `tests/unit/test_api.py::test_a_batch_answers_exactly_as_one_by_one`<br>`tests/unit/test_api.py::test_a_batch_answers_each_loan_on_its_own`<br>`tests/unit/test_api.py::test_a_malformed_batch_is_refused_whole`<br>`tests/unit/test_api.py::test_broken_json_is_refused` | Unit | CI, image |
| T18.5 | Keys (D-118): no key or a wrong key gives 401; the predict key does not open `/admin/reload` (403); two valid keys at once (rotation); `/health` needs no key; the key is never stored nor logged, only the client's name; keys shorter than 32 characters, repeated or malformed stop the start | `tests/unit/test_api.py::test_keys_decide_who_may_call_what`<br>`tests/unit/test_api.py::test_short_or_malformed_keys_stop_the_start` | Unit | CI, image |
| T18.6 | Duplicates (D-114): the same loan with the same versions twice gives one row and the same answer, marked as stored earlier; with a new champion, a new row | `tests/integration/test_api.py::test_the_same_loan_and_pair_is_stored_once` | Integration | CI |
| T18.7 | Synchronous writing (D-121): no prediction leaves without its stored row (in memory); with Postgres down, 503 and no prediction; a batch that fails halfway through its inserts leaves none of its loans stored | `tests/unit/test_api.py::test_no_prediction_leaves_without_being_stored`<br>`tests/integration/test_api.py::test_with_postgres_down_nothing_is_predicted`<br>`tests/integration/test_api.py::test_a_batch_that_fails_halfway_stores_nothing` | Unit, integration | CI, image |
| T18.8 | Start: the API is not ready (503) until it can load the champions, and becomes ready when the registry answers (in memory); it loads the champion trio from the MLflow server and `/health` shows the versions | `tests/unit/test_api.py::test_the_api_is_not_ready_until_it_can_load_the_champions`<br>`tests/integration/test_api.py::test_the_champions_come_from_the_mlflow_registry` | Unit, integration | CI, image |
| T18.9 | Reload (D-111): after a promotion `/admin/reload` serves the new pair at once; polling finds a moved alias without the notice (interval shortened); a champion that fails to load leaves the pair in use and writes one `model_load_failed` alert; with concurrent requests during the swap, none mixes versions | `tests/unit/test_api.py::test_a_new_champion_is_served_at_once_after_the_notice`<br>`tests/unit/test_api.py::test_polling_finds_a_new_champion_without_the_notice`<br>`tests/unit/test_api.py::test_a_champion_that_fails_to_load_leaves_the_pair_in_use`<br>`tests/unit/test_api.py::test_no_request_mixes_two_pairs_during_a_swap` | Unit | CI, image |
| T18.10 | A buy rule of another PD and LGD pair, or no rule yet: the risk is served and the threshold is "not available" | `tests/unit/test_api.py::test_a_rule_of_another_pair_gives_no_threshold`<br>`tests/unit/test_api.py::test_no_rule_yet_gives_no_threshold` | Unit | CI, image |
| T18.11 | What is stored: the row of `serving.predictions` has the request, the 30 features the model saw and the SHAP vector, and base value plus contributions gives the PD (additivity); the row of `serving.requests` has endpoint, status, latency, client and number of loans, and no free text of valid requests | `tests/integration/test_api.py::test_what_is_stored_with_each_prediction` | Integration | CI |
| T18.12 | Logs: one JSON line per request with id, path, status, latency and versions, with no key and no body | `tests/unit/test_api.py::test_one_json_line_per_request_without_keys_or_bodies` | Unit | CI, image |
| T18.13 | Load (D-122): the API in its own process takes an open load of 20 single-loan requests a second for 60 s with p95 under 200 ms; the capacity (answers a second with 20 busy clients for 20 s) is measured and printed with no assertion; a batch of 1,000 loans takes under 30 s | `tests/integration/test_api.py::test_latency_under_load` | Integration | CI |
| T18.14 | The API runs in compose from the `serve` image with its healthcheck: healthy, alive, the database reachable, the package version, and 401 with no key. B5 (800 MB) and B7 (no training libraries) keep checking that image | `tests/integration/test_api.py::test_the_api_runs_in_compose_from_the_serve_image` | Integration | CI |
| T18.15 | Data test: the real delivery of 2014-02 (15,269 loans), sent as the provider wrote it in batches of 1,000 to an API serving models trained at T0, gives exactly what scoring the month in process gives, with no refusal; every answer is stored | `tests/data/test_api_data.py::test_a_real_month_through_the_api_equals_scoring_in_process` | Data | Local |

## T19 Buy rule in the flow

F5, step 5.1, first pull request (D-111, D-120). Integration tests: the monthly flow runs in process against a database of its own and the MLflow server, on the small made-up source; a small HTTP server stands in for the API and records what it receives.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T19.1 | When the PD or LGD champion changes, the flow registers a buy rule with the minimum chosen on validation (D-084) and the versions of the pair, with every required field of its run (D-079), moves its alias and records a `promoted` alert; running the month again creates no version; a new PD champion makes a new rule, and going back reuses the old one | `tests/integration/test_buy_rule.py::test_the_flow_registers_the_rule_of_the_champion_pair` | Integration | CI |
| T19.2 | After a promotion the flow calls `/admin/reload` with the admin key, and a run with no change sends no notice; with an API that does not answer the flow goes on and records one `reload_failed` warning, without the key | `tests/integration/test_buy_rule.py::test_the_flow_tells_the_api_after_a_promotion` | Integration | CI |

## T20 Purchases

F5, old step 4.2, second pull request (D-124, D-126, D-128, D-129). Unit tests run the application in process on made-up champions with the in-memory store, as T18; T20.5 runs the same store against a migrated database of its own.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T20.1 | Every answer of `/predict` carries its `prediction_id`; a valid purchase (order, prediction, 25 dollars) gets 200 with status `created` and is stored with client, loan, prediction, amount and order number | `tests/unit/test_purchases.py::test_a_purchase_of_a_stored_prediction_is_recorded` | Unit | CI, image |
| T20.2 | Idempotency (D-129): the same order twice gives one row and the same purchase, marked `stored_earlier`; the same order number with another content is refused with 409; a new order on the same loan adds to the share (a repurchase); another client can buy the same loan, even with the same order number | `tests/unit/test_purchases.py::test_an_order_number_makes_a_repeat_harmless_and_allows_repurchases` | Unit | CI, image |
| T20.3 | Refusals per purchase (422, with the column), the rest of the request recorded: an unknown prediction id, an amount that is not a multiple of 25, zero, negative, not a whole number or missing, a client's share above the loan's amount, an unknown field, an empty order number; the request row keeps the refused body and errors. A malformed request (more than the limit, empty, not a list, a wrong key) is refused whole; no key or a wrong key gives 401, the admin key 403 | `tests/unit/test_purchases.py::test_a_wrong_purchase_is_refused_on_its_own`<br>`tests/unit/test_purchases.py::test_a_malformed_request_is_refused_whole`<br>`tests/unit/test_purchases.py::test_purchases_need_a_predict_key` | Unit | CI, image |
| T20.4 | Exceptions are recorded, not refused (D-126): a purchase that passes the threshold, one below it, one with no threshold and one of an uncovered term are all accepted, with their `policy` | `tests/unit/test_purchases.py::test_exceptions_to_the_rule_are_recorded_not_refused` | Unit | CI, image |
| T20.5 | With the real Postgres: the unique (client, order number) is in the database; each request leaves its row in `serving.requests` with client and counts; two requests at once with the same order leave one row, and two orders at once that each fill a loan leave one; a request that fails halfway records no purchase and no request | `tests/integration/test_purchases.py::test_the_database_keeps_one_row_per_order_and_whole_requests`<br>`tests/integration/test_purchases.py::test_two_requests_at_once_cannot_duplicate_an_order_or_overfill_a_loan`<br>`tests/integration/test_purchases.py::test_a_request_that_fails_halfway_records_nothing` | Integration | CI |

## T21 Simulated investor

F5, old step 4.2, second pull request (D-123, D-125, D-127). T21.1 is a unit test of the rule; T21.2 to T21.5 check the clock story of `tests/integration/test_clock.py` (T17), where the API now runs in a process of its own, batches are of 4 listings so that each month takes several, and one advance of 2012-04 finds the API out of reach.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T21.1 | The investor's rule by hand (D-085): K is 10% of the loans listed the month before, rounded down; the loans that pass the threshold are bought in listing order until K, 25 dollars each; an uncovered loan or one below the minimum is never bought; with fewer passing than K all are bought, with K above the whole month only those that pass, and with no buy rule nothing; the same as `business.buy` on the same loans | `tests/unit/test_replayer.py::test_the_investor_buys_what_passes_in_listing_order_up_to_k` | Unit | CI, image |
| T21.2 | Months (D-127): nothing up to T0 is sent to the API; from the month after, every listing of each month is sent, in batches never above the limit, and has exactly one prediction | `tests/integration/test_clock.py::test_the_investor_sends_every_listing_after_t0_once` | Integration | CI |
| T21.3 | Order inside `advance` (D-123): the loans of the retraining month 2012-04, and of 2012-05, are scored by the champions promoted before that month | `tests/integration/test_clock.py::test_a_month_is_scored_by_the_champions_of_the_month_before` | Integration | CI |
| T21.4 | Failures (D-125): with the API out of reach, the investor's task runs 1 + 3 times (waits set to 0), the advance fails and the clock stays; the next advance does the month; a month repeated after the system's flow failed is not sent again; an investor that stopped after buying sends the month again with no prediction or purchase stored twice; a listing the API refuses is not bought, is counted in the month's summary and the month completes | `tests/integration/test_clock.py::test_the_investor_retries_a_missing_api_and_never_buys_twice` | Integration | CI |
| T21.5 | The whole story: for every month invested, the purchases in `serving.purchases` are exactly what the rule gives on the predictions in `serving.predictions` (same loans, linked to their predictions, 25 dollars, `passes`), and `sim.invested` has its counts; no loan is bought twice | `tests/integration/test_clock.py::test_what_was_bought_is_what_the_rule_gives_on_the_predictions` | Integration | CI |

## T22 Delivery

F5, step 5.2, third pull request (D-130 to D-136). What runs only on main (the job `publish`) is checked here on every pull request: its rules in the YAML (T22.2), its smoke test on the images just built (T22.3) and its program against a registry of its own (T22.4). The smoke test and the rehearsal start their own services under a compose project of their own, on free ports, and remove them at the end.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T22.1 | Names and tags (D-132): main gives `sha-` and 7 characters of the commit, then `main`; a tag `vX.Y.Z` gives the same commit tag, reused, then `X.Y.Z`; the owner is lowercase for GHCR; a tag that is not the version of `pyproject.toml`, not of the form `vX.Y.Z`, another branch, a pull request or a commit that is not a full hash publish nothing and say why; a release of a commit with no published images fails and changes nothing | `tests/unit/test_release.py::test_main_publishes_the_commit_tag_and_then_moves_main`<br>`tests/unit/test_release.py::test_a_release_tag_reuses_the_commit_and_adds_its_version`<br>`tests/unit/test_release.py::test_anything_else_publishes_nothing_and_says_why`<br>`tests/unit/test_release.py::test_a_release_of_a_commit_never_published_from_main_fails` | Unit | CI, image |
| T22.2 | The rules in the workflows (D-133, D-135): `publish` needs the four jobs and runs only on a push to main or a tag `v*`; only it can write packages, every other job reads; it builds nothing and takes the images the integration job saved; Trivy (HIGH and CRITICAL, blocking, with the exceptions file) runs before the publication; runs are cancelled only on pull requests; every action is pinned by its commit; the Monday scan reads the published `main` images | `tests/unit/test_workflows.py::test_publish_runs_only_on_main_and_releases_after_the_four_jobs`<br>`tests/unit/test_workflows.py::test_only_publish_can_write_packages`<br>`tests/unit/test_workflows.py::test_publish_builds_nothing_and_goes_scan_push_smoke_promote`<br>`tests/unit/test_workflows.py::test_every_action_is_pinned_by_its_commit`<br>`tests/unit/test_workflows.py::test_the_weekly_scan_reads_the_published_main_images` | Unit | CI, image |
| T22.3 | The smoke test (D-134) on the images of the pull request: it passes on good images (`/health` 200, a prediction with PD and LGD in range, train carrying its commit); it fails, saying where, when the API never gets ready (no champion: `/health` 503) and when train carries another commit; it leaves no service behind | `tests/integration/test_smoke.py::test_the_smoke_test_passes_on_good_images_and_leaves_nothing`<br>`tests/integration/test_smoke.py::test_the_smoke_test_fails_when_the_api_never_gets_ready`<br>`tests/integration/test_smoke.py::test_the_smoke_test_fails_when_train_carries_another_commit` | Integration | CI |
| T22.4 | Rehearsal of the publication against a throwaway registry (D-132 to D-134): the images pulled back are the tested ones and `main` points to their digest; a failed smoke test leaves `main` where it was and the failed images under their commit; the tag of a commit is never rewritten with other images; a release tags the published images with the version without pushing anything else | `tests/integration/test_release.py::test_the_published_images_are_the_tested_ones_and_main_points_to_them`<br>`tests/integration/test_release.py::test_a_failed_smoke_test_leaves_main_where_it_was`<br>`tests/integration/test_release.py::test_the_tag_of_a_commit_is_never_rewritten`<br>`tests/integration/test_release.py::test_a_release_tags_the_published_images_without_pushing` | Integration | CI |
| T22.5 | The brakes of the publication program, with a registry in memory: an image that was not tested is never pushed; an image pulled back that is not the tested one, a version already on another image, or a moved tag on another digest (E-051) stop the publication without moving `main`; a repeated run of the same commit finishes without pushing again; a fresh pull drops the local copies first; the answers of `docker` become clear errors ("not found" is absence, anything else stops); the command line exits 1 with the reason, and on success writes the summary of what it published | `tests/unit/test_publish.py::test_an_image_that_was_not_tested_is_never_pushed`<br>`tests/unit/test_publish.py::test_an_image_pulled_back_that_is_not_the_tested_one_stops_everything`<br>`tests/unit/test_publish.py::test_a_version_already_on_another_image_is_never_rewritten`<br>`tests/unit/test_publish.py::test_a_moved_tag_that_lands_on_another_digest_is_reported`<br>`tests/unit/test_publish.py::test_a_repeated_run_of_the_same_commit_finishes_without_pushing_again`<br>`tests/unit/test_publish.py::test_a_fresh_pull_drops_the_local_copies_before_pulling`<br>`tests/unit/test_publish.py::test_answers_of_docker_become_clear_errors`<br>`tests/unit/test_publish.py::test_the_command_line_says_why_it_stops_and_summarises_what_it_published` | Unit | CI, image |
| T22.6 | The admin key of the API in compose (D-111, D-118): every service of the `train` image is classified as running the monthly flow (worker, clock) or not (MLflow, Prefect), so a new one forces the choice; the two that run it get `API_URL` and `API_ADMIN_KEY`, so after a promotion they can tell the API to reload; no other service gets the admin key | `tests/unit/test_compose.py::test_every_service_of_the_train_image_is_classified`<br>`tests/unit/test_compose.py::test_the_services_that_run_the_flow_can_tell_the_api_to_reload`<br>`tests/unit/test_compose.py::test_no_other_service_has_the_admin_key` | Unit | CI, image |

## T23 Drift

F6, step 6.1, first pull request (D-139, D-140). Pure functions of `credit_risk/monitoring/drift.py` on the made-up loans of the training tests, turned into the 30 features by `credit_risk.features`.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T23.1 | The PSI of a distribution against itself is 0, and the two worked examples of `grade` given to Juan give 0.052 and 0.272; shares over different bins are refused | `tests/unit/test_monitoring.py::test_psi_is_zero_for_the_same_shares_and_matches_the_hand_examples` | Unit | CI, image |
| T23.2 | No change, no drift: two samples of 20,000 loans of the same distribution give a PSI under 0.01 in each of the 30 features | `tests/unit/test_monitoring.py::test_two_samples_of_the_same_distribution_show_no_drift` | Unit | CI, image |
| T23.3 | An injected change is seen in that variable only: `int_rate` 2 points higher, or grade D more than doubled (the second example), gives a PSI above 0.25 in it and under 0.01 in every other feature | `tests/unit/test_monitoring.py::test_an_injected_change_is_seen_in_that_variable_only` | Unit | CI, image |
| T23.4 | The bins come from the reference: cut at its deciles, a value out of range falls in the bin at that end, a value equal to a cut point in the bin that ends there, and a variable that is almost always 0 gets its cut points once and no empty twin bins | `tests/unit/test_monitoring.py::test_bins_are_cut_at_the_deciles_of_the_reference` | Unit | CI, image |
| T23.5 | Missing and new values have their own bins: a category never seen is counted as new and moves the PSI; an empty bin counts with the floor of 0.01%, never infinity; numbers outside the range of the reference are new, missing ones (null or NaN) go to their bin | `tests/unit/test_monitoring.py::test_missing_and_new_values_have_their_own_bin` | Unit | CI, image |
| T23.6 | The KS statistic is that of `scipy.stats.ks_2samp` against the reference sample, which is the whole reference up to 5,000 values and a fixed draw above; none for categorical variables | `tests/unit/test_monitoring.py::test_ks_is_the_scipy_statistic_against_the_reference_sample` | Unit | CI, image |

## T24 Monitoring reference

F6, step 6.1, first pull request (D-138, D-142). On the clock story of `tests/integration/test_clock.py` (T17), where the flow builds the references.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T24.1 | Every pair of champions that answered, and the pair in service, has a reference with the cutoff of its later model and the listings of cutoff - 12 to cutoff - 1, one row per watched variable; none is deleted; the first pair, trained at T0 (2012-01), has 2011 | `tests/integration/test_clock.py::test_each_pair_of_champions_has_the_reference_of_the_12_months_before_its_cutoff` | Integration | CI |
| T24.2 | The reference scores a loan exactly as the API did: for the loans of 2012-02, the PD, the LGD and the expected loss rate of the reference are those stored by the API | `tests/integration/test_clock.py::test_the_reference_scores_a_loan_exactly_as_the_api_did` | Integration | CI |
| T24.3 | Building a reference writes nothing to `serving.predictions`, `serving.requests` or `serving.purchases`, and is done once per pair | `tests/integration/test_clock.py::test_building_a_reference_writes_nothing_to_the_predictions` | Integration | CI |

## T25 Early warning

F6, step 6.1, first pull request (D-143). The share of first-year defaults by hand (unit) and from the database (integration); the cohort with loans written straight into Postgres.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T25.1 | The share of the defaults that came in the first year, by term and grade, matches the hand computation; a grade with fewer than 50 defaults takes the share of its term; in the database, only the cohorts matured at the cutoff, their defaults delivered by then and the statuses of the current policy count | `tests/unit/test_monitoring.py::test_first_year_share_by_term_and_grade_with_the_term_for_small_grades`<br>`tests/integration/test_monitoring.py::test_the_first_year_share_is_measured_on_the_cohorts_matured_at_the_cutoff` | Unit, integration | CI |
| T25.2 | Only labels already delivered count: cohort c is measured in month c + 17 with the outcomes delivered by then; an early default delivered later does not count; a last payment at issue + 11 is early, at issue + 12 is not; before c + 17 the cohort has no row | `tests/integration/test_monitoring.py::test_the_early_warning_counts_only_the_outcomes_delivered_by_its_month` | Integration | CI |
| T25.3 | The ratio and its 95% Wilson interval: observed equal to expected gives an interval around 1, twice gives one above 1; the interval against its formula and at both edges (E-057); the AUC on the 12-month default | `tests/unit/test_monitoring.py::test_the_ratio_and_its_wilson_interval` | Unit | CI, image |
| T25.4 | Each cohort is measured with the PD version that predicted it, with the first-year share at that version's cutoff; a loan scored again later counts with its first answer | `tests/integration/test_monitoring.py::test_each_cohort_is_measured_with_the_model_version_that_predicted_it` | Integration | CI |

## T26 Real performance

F6, step 6.1, first pull request (D-144).

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T26.1 | A cohort is measured only when it matures (term + 5) and with the outcomes delivered by then: one arriving later is unresolved; the LGD only on defaults resolved at least 12 months before; a 60-month loan of the same cohort is not measured yet | `tests/integration/test_monitoring.py::test_a_cohort_is_measured_when_it_matures_with_the_outcomes_known_then` | Integration | CI |
| T26.2 | The metrics are those of F3 for the same data: AUC, Brier score and calibration error overall and by grade as `credit_risk.compare`; RMSE and level of the LGD; the realised return of the purchases as `credit_risk.business` | `tests/unit/test_monitoring.py::test_performance_uses_the_metrics_of_promotion_and_the_returns_of_business` | Unit | CI, image |

## T27 Monitoring in the flow

F6, step 6.1, first pull request (D-145, D-146). T27.2, T27.4 and T27.5 on the clock story of `tests/integration/test_clock.py`.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T27.1 | The migration of `monitoring` goes up, down and up again; the tables refuse impossible rows: a negative PSI, a drift of a variable with no reference, an interval whose lower end is above the ratio, an early warning not measured at cohort + 17 | `tests/integration/test_monitoring.py::test_the_monitoring_tables_migrate_and_refuse_impossible_rows` | Integration | CI |
| T27.2 | `monitor` runs every month right after `load` and before `version`; T0, with no predictions yet, is noted and does not fail | `tests/integration/test_clock.py::test_monitor_runs_every_month_after_load_and_before_training` | Integration | CI |
| T27.3 | Measuring a month again gives the same rows, not more; after an outcome changes, running the month again replaces its rows | `tests/integration/test_monitoring.py::test_measuring_a_month_again_replaces_its_rows` | Integration | CI |
| T27.4 | A failed `monitor` fails the month: a `flow_failed` alert names the task and its error, the clock does not move, and the next advance does the month | `tests/integration/test_clock.py::test_a_failed_monitor_fails_the_month_and_the_clock_stays` | Integration | CI |
| T27.5 | Every month of the story with predictions keeps its drift: 33 rows (30 features, 3 predictions) per pair that answered; T0 has none | `tests/integration/test_clock.py::test_every_month_with_predictions_keeps_its_drift` | Integration | CI |

## T28 Monitoring on the real data

F6, step 6.1, first pull request (D-143, D-145). Local only, like every data test.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| T28.1 | The share of first-year defaults on the cohorts matured at T0 agrees with the audit: 41% for 36 months, within 5 points; only 36-month loans have matured | `tests/data/test_monitoring_data.py::test_the_first_year_share_at_t0_agrees_with_the_audit` | Data | Local |
| T28.2 | The real year of T17.9: every month from 2014-02 to 2014-12 has its drift for the 30 features and the 3 predictions of each pair that answered, and T0 none; it prints the largest PSI of each month without fixing any value (thresholds are for 6.2) | `tests/data/test_clock_data.py::test_every_month_of_the_real_year_with_predictions_has_its_drift` | Data | Local |

## Change history

| Date | Test | Change | Why |
|---|---|---|---|
| 2026-11-22 | B1, B2 | Written (step 1.1) | Approved by Juan |
| 2026-11-22 | B3 to B5 | Written (step 1.2); B5 budget 300 MB | Approved by Juan |
| 2026-11-23 | T1.1 to T1.12, T2.1 to T2.11, T3.1 to T3.13 | Written (step 2.1) | Approved by Juan |
| 2026-11-23 | B5 | Image budget raised from 300 MB to 500 MB | polars adds 170 MB and the API needs it ([D-052](decisions.md#d-052)) |
| 2026-11-23 | T4.1 to T4.16 | Written (step 2.2) | Approved by Juan |
| 2026-11-23 | T3.2 to T3.12 | Fixtures start from rows that pass validation (`tests/valid_rows.py`); `build_clean` builds a month; T3.9's outcome now has a late fee that matches its payments; T3.10 deletes the validation rows of the month first. What each test checks is unchanged | Validation runs inside every load and the month is the unit ([D-055](decisions.md#d-055)) |
| 2026-11-23 | B6 | Written; markers `# B1` to `# B5`, `# T1.12`, `# T2.11` and `# T4.16` added to the code | Approved by Juan: tests documented like decisions and errors, kept in step mechanically |
| 2026-11-23 | T3.14, T3.15 | Numbered: two functions written in step 2.1 without being presented as tests (the autocommit guard and the `COPY` measurement of D-047) | Found while writing this catalogue; approved by Juan |
| 2026-11-23 | B6 | Also fails if a test function in `tests/` is in no row | Approved by Juan with T3.14 and T3.15: no test enters without being catalogued |
| 2026-11-23 | T5.1 to T5.14 | Written (step 2.3) | Approved by Juan |
| 2026-11-23 | T5.13 | Expected counts changed from the audit's (12,078; train 7,745; validation 4,333 with 432 defaults) to those known at T0, plus a reconciliation with the audit | The audit used outcomes resolved after T0 ([E-022](errors.md#e-022)); approved by Juan |
| 2026-11-23 | T6.1 to T6.8 | Written (step 2.4) | Approved by Juan |
| 2026-11-23 | T3.13, T3.15, T4.15 | The full real load moved to `tests/data/conftest.py`, done once per session and shared with T6.8. What each test checks is unchanged | Loading the 142 months takes about 6 minutes; doing it twice is waste |
| 2026-11-24 | T5.4, T5.5, T5.12, T5.13, T5.15 | T5.13 also checks that T0 holds 36-month loans only and counts the loans with `lgd`; T5.4 checks the validation window per term; T5.5 expects the `lgd` column; T5.12 mirrors both rules in polars; T5.15 written | Approved by Juan ([D-069](decisions.md#d-069), [D-088](decisions.md#d-088)) |
| 2026-11-24 | T5.1 | One training loan added to its data. What it checks is unchanged | Under D-069 its two loans are both validation, and a set with no training loan is refused |
| 2026-11-24 | B5 | Runs on both images, `serve` (budget 800 MB) and `train` (1.5 GB); the size is the sum of the layers instead of `docker image inspect` | Two images ([D-078](decisions.md#d-078)); the inspected size depends on the Docker image store ([E-028](errors.md#e-028)). Approved by Juan |
| 2026-11-24 | T7.1 to T7.5, T8.1 to T8.4, T9.1 to T9.4, T10.1 to T10.6, T11.1 to T11.5, T12.1 to T12.6, B7, B8 | Written (F3, second pull request) | Approved by Juan |
| 2026-11-24 | T9.3 | Case added: clearly worse in a segment but within the margin passes | The margins of [D-093](decisions.md#d-093); approved by Juan |
| 2026-11-24 | T5.13, T5.14 | The load up to T0 moved from `tests/data/test_snapshot_data.py` to `tests/data/conftest.py`, shared with T10.6 and T12.6. What each test checks is unchanged | The load takes minutes; doing it twice is waste |
| 2026-11-24 | T12.6, T12.7 | T12.6 no longer checks that the mean predicted LGD lies inside the interval of the observed mean (true by construction after D-094): it checks the mean after the correction and that no shift exceeds 0.10, and logs the gap before. T12.7 written | The LGD was 5 points too low at T0 and its level is now corrected on validation ([D-094](decisions.md#d-094)); approved by Juan |
| 2026-11-24 | T13.1 to T13.5 | Written (F3, third pull request) | Approved by Juan |
| 2026-11-24 | T10.4 | Times each prediction together with its explanation | The PD is served with its reasons ([D-083](decisions.md#d-083)); approved by Juan |
| 2026-11-24 | T14.1 to T14.6 | Written (F3, third pull request) | Approved by Juan |
| 2026-11-24 | T15.1 to T15.7 | Written (F3, third pull request) | Approved by Juan |
| 2026-11-24 | T16.1 to T16.10 | Written (F4, first pull request) | Approved by Juan |
| 2026-11-24 | B7 | Also checks that `serve` cannot import Prefect | Prefect enters the `train` group ([D-103](decisions.md#d-103)); approved by Juan with T16 |
| 2026-11-24 | T16.7, T16.10 | T16.7: the test publishes the deliveries with the simulator before the flow, which no longer has a publish task. T16.10: the failing run of the deployment fails in the load task (no deliveries) instead of the publish task | Publishing belongs to the simulated world, not to the system ([D-105](decisions.md#d-105)); approved by Juan with D-105 |
| 2026-11-24 | T16.8 | Raw is left out of the "nothing new" comparison | Raw keeps every delivery as it came, by design ([D-044](decisions.md#d-044)); validation stops it at clean ([E-040](errors.md#e-040)) |
| 2026-11-24 | T17.1 to T17.9 | Written (F4, second pull request) | Approved by Juan |
| 2026-11-24 | T18.1 to T18.15, T19.1, T19.2 | Written (F5, first pull request) | Approved by Juan |
| 2026-11-24 | T18.13 | Open load of 20 requests a second for 60 s with p95 under 200 ms instead of 20 clients firing without pause; capacity measured and recorded, with no assertion | 20 busy clients measure saturation, not latency: each request waits for the other 19 ([D-122](decisions.md#d-122), [E-044](errors.md#e-044)); approved by Juan |
| 2026-11-24 | T16.8, T17.6 | T16.8: `buy-rule` and `reload` never run after a failed validation either. T17.6: the retraining months also run `buy-rule`, and `reload` when a champion or the rule changed | The flow gained these two tasks ([D-111](decisions.md#d-111), [D-120](decisions.md#d-120)). What each test checks is unchanged |
| 2026-11-25 | T20.1 to T20.5, T21.1 to T21.5 | Written (F5, second pull request) | Approved by Juan |
| 2026-11-25 | T17.9 | Also checks the investor: from 2014-02 every listing has one prediction through the API, no month buys more than K, and the purchases are what the rule gives; the API runs in a process of its own during the replay | The replayer lives inside the clock ([D-123](decisions.md#d-123)); checked on the real year rather than repeating its 25 minutes in another test. Approved by Juan |
| 2026-11-25 | T17.4 to T17.8 | The clock story runs with an API in a process of its own, batches of 4 listings and one more advance of 2012-04 with the API out of reach. What each test checks is unchanged | Each advance now sends its month to the API ([D-123](decisions.md#d-123)); approved by Juan with T21 |
| 2026-11-25 | T18.6 to T18.8, T18.11, T18.13 | T18.13: the API process is started by `tests/integration/api_process.py`, shared with the clock story. The module's fixture also empties `serving.purchases`, which refers to the predictions. What each test checks is unchanged | The same server is needed by T21; the new table of [D-124](decisions.md#d-124) |
| 2026-11-25 | T22.1 to T22.4 | Written (F5, third pull request). T22.1 also checks the release of a commit never published; T22.4 also the release without pushing and the commit tag never rewritten | Approved by Juan; the two cases were added the same day, when the implementation showed a release must not build again ([D-132](decisions.md#d-132), [D-133](decisions.md#d-133)) |
| 2026-11-25 | T22.5 | Written (F5, third pull request) | The rule of 90% of changed lines covered ([D-064](decisions.md#d-064)) showed that the brakes of `ci/publish.py`, which only fire when something goes wrong, had no test; approved by Juan |
| 2026-11-25 | T18.12 | The value that must not reach the log is `term="sixty months please"`, no longer `term="bad"`. What the test checks is unchanged | It failed at random on main: a random request id held "bad" ([E-053](errors.md#e-053)); approved by Juan |
| 2026-11-25 | T22.6 | Written (F5, after the first publication) | The clock had no admin key in compose and no test read compose ([E-056](errors.md#e-056)); Juan chose a unit test on compose over a slower integration test, and approved it |
| 2026-11-26 | T23.1 to T23.6, T24.1 to T24.3, T25.1 to T25.4, T26.1, T26.2, T27.1 to T27.5, T28.1, T28.2 | Written (F6, first pull request) | Approved by Juan |
| 2026-11-26 | T16.8, T17.6 | T16.8: `monitor` and `reference` never run after a failed validation either. T17.6: every month runs `monitor` after `load`, and the retraining months also `reference`. What each test checks is unchanged | The flow has two more tasks ([D-145](decisions.md#d-145), [D-142](decisions.md#d-142)) |
