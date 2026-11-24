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
- [Change history](#change-history)

## How tests are organised

Tests are grouped by the piece they check. Group B holds the foundations of F1 (package, settings, Postgres, image); each group T*n* belongs to a step of F2. Every test has an ID; a test can be one or more pytest functions.

| Kind | Folder | pytest marker | Needs | Command | Runs in |
|---|---|---|---|---|---|
| Unit | `tests/unit/` | none | Nothing | `make test`, `make test-image` | CI (job `tests`), and inside the image (job `integration`) |
| Integration | `tests/integration/` | `integration` (`destructive` for B4) | Docker: compose Postgres or the built image | `make test-integration` | CI (job `integration`) |
| Data | `tests/data/` | `data` | The real Lending Club file and its deliveries in `data/` (and Postgres for T3.13, T3.15, T4.15, T5.13, T5.14, T6.8) | `make test-data` | Local only: the file is 1.6 GB and Kaggle needs a token |

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
| B Foundations | F1, steps 1.1 and 1.2 | 6 | 2026-11-22 (B1 to B5), 2026-11-23 (B6) | [technical.md, F1](technical.md#3-f1-foundations) |
| T1 Simulator | F2, step 2.1 | 12 | 2026-11-23 | [technical.md, step 2.1](technical.md#step-21-idempotent-ingestion) |
| T2 Cleaning | F2, step 2.1 | 11 | 2026-11-23 | [technical.md, step 2.1](technical.md#step-21-idempotent-ingestion) |
| T3 Loading | F2, step 2.1 | 15 | 2026-11-23 (T3.14 and T3.15 on approval in step 2.2) | [technical.md, step 2.1](technical.md#step-21-idempotent-ingestion) |
| T4 Validation | F2, step 2.2 | 16 | 2026-11-23 | [validation_rules.md](validation_rules.md), [technical.md, step 2.2](technical.md#step-22-data-validation) |
| T5 Training set versions | F2, step 2.3; F3 (D-069, D-088) | 15 | 2026-11-23; 2026-11-24 (T5.4, T5.5, T5.12, T5.13 changed, T5.15 added) | [technical.md, step 2.3](technical.md#step-23-data-versioning) |
| T6 Features | F2, step 2.4 | 8 | 2026-11-23 | [technical.md, step 2.4](technical.md#step-24-features) |
| **Total** | | **83** | | |

## B Foundations

F1, steps 1.1 and 1.2.

| ID | What it checks | Functions | Kind | Runs in |
|---|---|---|---|---|
| B1 | The package imports and its version is read from `pyproject.toml`, its only source | `tests/unit/test_version.py::test_package_version_matches_pyproject` | Unit | CI, image |
| B2 | Settings come from the environment; a missing variable fails with its name; the password never appears in `str()`, `repr()` or JSON | `tests/unit/test_settings.py::test_settings_read_from_env`<br>`tests/unit/test_settings.py::test_settings_missing_variable_fails_clearly`<br>`tests/unit/test_settings.py::test_settings_never_expose_password` | Unit | CI, image |
| B3 | Our settings connect to the compose Postgres and `SELECT 1` returns 1; the server's major version is 18 | `tests/integration/test_postgres.py::test_postgres_accepts_connection`<br>`tests/integration/test_postgres.py::test_postgres_major_version_is_18` | Integration | CI |
| B4 | A random value in a table with a random name survives `docker compose down` + `up` (a new container); the table is dropped afterwards. Marked `destructive`: runs last and alone | `tests/integration/test_persistence.py::test_postgres_data_survives_container_recreation` | Integration | CI |
| B5 | The image runs as non-root, has no `.env*` file, no secret in its configuration or build history, prints the right version, and is at most 500 MB | `tests/integration/test_image.py::test_image_runs_as_non_root`<br>`tests/integration/test_image.py::test_image_has_no_env_file`<br>`tests/integration/test_image.py::test_image_has_no_secrets_in_config`<br>`tests/integration/test_image.py::test_image_default_command_works`<br>`tests/integration/test_image.py::test_image_size_within_budget` | Integration | CI |
| B6 | Every test marker in `tests/` is in this catalogue and the other way round, in the same file; every function named here exists; every test function in `tests/` is named here | `tests/unit/test_catalogue.py::test_markers_and_catalogue_agree` | Unit | CI, image |

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
