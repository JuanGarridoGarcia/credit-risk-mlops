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
- [Change history](#change-history)

## How tests are organised

Tests are grouped by the piece they check. Group B holds the foundations of F1 (package, settings, Postgres, image); each group T*n* belongs to a step of F2. Every test has an ID; a test can be one or more pytest functions.

| Kind | Folder | pytest marker | Needs | Command | Runs in |
|---|---|---|---|---|---|
| Unit | `tests/unit/` | none | Nothing | `make test`, `make test-image` | CI (job `tests`), and inside the image (job `integration`) |
| Integration | `tests/integration/` | `integration` (`destructive` for B4) | Docker: compose Postgres or the built image | `make test-integration` | CI (job `integration`) |
| Data | `tests/data/` | `data` | The real Lending Club file and its deliveries in `data/` (and Postgres for T3.13, T3.15, T4.15) | `make test-data` | Local only: the file is 1.6 GB and Kaggle needs a token |

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
| **Total** | | **60** | | |

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
