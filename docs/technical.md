# Technical document

The full detail of the project, one section per step of the playbook: what was built, how, which numbers came out, which decisions and errors happened, and how it was checked. The README is the short version; this is the manual. Format decided in D-035.

Related documents: [problem definition](problem.md), [data audit](data_audit.md), [decision log](decisions.md), [error log](errors.md), [validation rules](validation_rules.md), [test catalogue](tests.md).

## Contents

1. Tracking sheet
2. F0 Framing (steps 0.1, 0.2)
3. F1 Foundations (steps 1.1 to 1.4)
4. F2 Data (steps 2.1 to 2.4)
5. F3 Model (steps 3.1 to 3.5)

---

## 1. Tracking sheet

Status of every step of the playbook. Updated in every pull request.

| Phase | Step | Status | PR | Notes |
|---|---|---|---|---|
| F0 Framing | 0.1 Problem, metric, baseline and constraints | Done | #1 | D-001 to D-011 |
| | 0.2 Data audit | Done | #1 | D-012 to D-018; 9.4 to 9.6 decided in F2 (D-040 to D-042) |
| F1 Foundations | 1.1 Repository, environment and code quality | Done | #2 | D-019 to D-024, D-037 |
| | 1.2 Docker and docker compose | Done | #2 | D-025 to D-027 |
| | 1.3 Minimal CI | Done | #2 | D-028 to D-032, D-038. Lint-failure check done; branch protection set by Juan on 2026-11-22 |
| | 1.4 Documentation skeleton | Done | #2 | D-033 to D-036 |
| F2 Data | 2.1 Idempotent ingestion | Done | #5 | D-039 to D-052; E-013 to E-019 |
| | 2.2 Data validation | Done | #5 | D-053 to D-057; E-020, E-021; rules in validation_rules.md; tests in tests.md |
| | 2.3 Data versioning | Done | #5 | D-058 to D-061; E-022 |
| | 2.4 Features | Done | #5 | D-062, D-063; cross-cutting: coverage minimum D-064, audit notebook in CI D-065 |
| F3 Model | 3.1 Baseline | In progress | | Designed: D-067, D-069, D-070. Split per term (D-069) implemented in the data PR |
| | 3.2 Tracking and experiments | Designed | | D-068, D-071 to D-079, D-087, D-088 (LGD label implemented in the data PR) |
| | 3.3 Model tests and promotion rules | Designed | | D-080, D-081, D-086 |
| | 3.4 Model registry | Designed | | D-082 |
| | 3.5 Explainability and model card | Designed | | D-083; buy rule and budget D-084, D-085 |
| F4 Automation | 4.1 Orchestrated training flow | Pending | | |
| | 4.2 Batch prediction flow | Pending | | Replaced by the replayer calling the API (D-008) |
| F5 Deployment | 5.1 API | Pending | | |
| | 5.2 Published image and CD | Pending | | |
| F6 Monitoring | 6.1 Drift and metrics | Pending | | |
| | 6.2 Dashboard and alerts | Pending | | |
| | 6.3 Triggered retraining | Pending | | |
| F7 Closing | 7.1 End to end and reproducibility | Pending | | |
| | 7.2 Cloud and infrastructure as code | Pending | | |
| | 7.3 Final documentation | Pending | | |

---

## 2. F0 Framing

### Step 0.1 Problem, metric, baseline and constraints

Full detail in [`problem.md`](problem.md), approved by Juan on 2026-11-20. In short: an investor decides whether to buy each Lending Club loan when it is listed (D-001); the system serves PD, LGD and expected loss (D-002) through a single path, the API (D-008); the PD target is lifetime default, with the 12-month default rate as an early-warning signal (D-003); baselines use only the grade (D-004, D-005); models are judged on ranking and calibration (D-006) and the business on realised return at equal budget (D-007).

### Step 0.2 Data audit

Full detail in [`data_audit.md`](data_audit.md), produced by `notebooks/00_data_audit.ipynb`. Source pinned by SHA-256 (D-012); leakage rule: only fields proven visible at listing (D-014); label mapping (D-013), free text (D-015), late-starting fields (D-016), LGD label maturity (D-017) and the proxy review of `addr_state` and zip code (D-018). Errors E-001 to E-007.

---

## 3. F1 Foundations

Every decision of F1 was explained to Juan and taken by him one by one on 2026-11-22, and every test was approved before it was written.

### Step 1.1 Repository, environment and code quality

**Layout** (D-021)

```
credit-risk-mlops/
  src/credit_risk/          the system, as an installable package
    __init__.py             __version__, read from the installed metadata
    __main__.py             default command of the image (prints the version)
    settings.py             configuration from environment variables
  tests/
    unit/                   no external services
    integration/            need Docker (Postgres, the built image)
  config/                   parameters in files (from F2)
  docs/                     problem, audit, decisions, errors, this document
  notebooks/                exploration and report notebooks, never production code
  reports/                  generated tables and figures
  data/                     downloaded data, git-ignored
```

**Environment** (D-019, D-020, D-024). `pyproject.toml` declares three kinds of dependencies, all resolved together into `uv.lock`:

| Group | Contents | Where it is installed |
|---|---|---|
| main | `psycopg[binary]`, `pydantic-settings` | Everywhere, including the image |
| `dev` (default) | ruff, mypy, pytest, pytest-cov, pre-commit, pip-audit | Development and CI |
| `notebooks` | Exact F0 audit versions (polars 2.1.0, pandas 3.1.1, scikit-learn 1.9.1...) | Only to run notebooks |

Python 3.12 is fixed in `.python-version`, `requires-python` and the base image. All commands use `--frozen`, so the lock is never re-resolved silently; `make lint` checks the lock matches `pyproject.toml`.

**Version** (test B1). The only place where the version is written is `pyproject.toml`; the package reads it from its installed metadata. Every prediction stored from F5 on will carry this version.

**Settings** (test B2). `credit_risk.settings.Settings` (pydantic-settings) reads `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` from the environment. Missing required variables fail at start-up with their name; the password is a `SecretStr`, so it never appears in `str()`, `repr()` or JSON dumps.

**Code quality** (D-022, D-023). ruff with the rule sets E, W, F, I, B, UP, SIM, C4, PT, RUF, S (security), N, BLE, PTH, TID; line length 100. mypy strict on `src/`, with the pydantic plugin; tests are type-checked without requiring annotations. pre-commit hooks: see D-023. Pytest runs with `--strict-markers`, `--strict-config` and warnings as errors.

**Makefile**

| Command | What it does |
|---|---|
| `make install` | Environment from `uv.lock` (all groups), git hooks, `.env` from `.env.example` if missing |
| `make lint` | `uv lock --check`, ruff check, ruff format check, mypy |
| `make format` | Automatic fixes and formatting |
| `make test` | Unit tests with branch coverage |
| `make build` | Application image |
| `make test-image` | Unit tests inside the image, against the installed package |
| `make up` / `make down` | Start (and wait for healthy) / stop the services; data stays in the volume |
| `make test-integration` | Integration tests; the destructive one last and alone |
| `make audit` | pip-audit over every locked dependency |
| `make check` | Everything CI runs on a pull request |

**Audit notebook moved to the uv environment** (D-024). Re-run with the `notebooks` group: every number identical to F0. Two problems found and fixed on the way: outputs had no total order (E-010) and a variable was deleted while a function still read it (E-011). After the fix, two consecutive runs produced byte-identical outputs (2 min 18 s each, including the data download).

**Checks of the step**

| Check | Result |
|---|---|
| Trivial test runs in the test infrastructure | B1 passes locally, in CI and inside the image |
| `make lint` and `make test` work | Yes |
| pre-commit blocks a badly formatted file | Yes: a file with an unused import and bad formatting was rejected by `ruff check`, `ruff format` and `mypy`; the commit was not created |
| A clean clone installs with one command and passes lint and tests | Yes, see "Clean clone" below |

### Step 1.2 Docker and docker compose

**Image** (D-025, D-026). `Dockerfile` with four stages:

```
  uv        astral/uv:0.13.9 (by digest)       only to copy the uv binary
  builder   python:3.12.16-slim-trixie         uv sync --frozen --no-dev
              1) dependencies only  -> cached layer while the lock does not change
              2) the project, non-editable
  test      builder + dev tools, src/ deleted  unit tests against the installed package
  runtime   python:3.12.16-slim-trixie         /opt/venv only, user app (uid 10001)
```

The build context is limited by `.dockerignore` to `pyproject.toml`, `uv.lock`, `README.md`, `src/` and `tests/`: `.env`, data and git history never enter the build. Size: 211 MB.

**Services** (D-027). `docker-compose.yml` runs Postgres 18.7 (pinned by digest), with credentials from `.env`, the port bound to `127.0.0.1`, a `pg_isready` healthcheck every 2 seconds and the named volume `pgdata` mounted on `/var/lib/postgresql` (E-009). `make up` waits until the healthcheck passes.

**Tests**

| Test | File | What it checks |
|---|---|---|
| B3 | `tests/integration/test_postgres.py` | Our settings connect and `SELECT 1` returns 1; the server's major version is 18 |
| B4 | `tests/integration/test_persistence.py` | A random value in a table with a random name survives `docker compose down` + `up` (a new container, checked by its id); the table is dropped afterwards, pass or fail. Marked `destructive`, it runs last and alone |
| B5 | `tests/integration/test_image.py` | The image runs as non-root; no `.env*` file anywhere in it; no password, secret, token, Kaggle or AWS variable in its configuration or build history; the default command prints the right version; size at most 300 MB (measured 211 MB); raised to 500 MB in F2 (D-052, 456 MB with polars) |

Each integration test opens its own database connection, so B4 cannot break another test's connection. Integration tests never skip: if Docker or Postgres is missing they fail.

**Building in Claude's cloud machine** (E-008): `DOCKER_BUILD_FLAGS="--network host --build-arg HTTPS_PROXY=... --secret id=extra_ca,src=<proxy CA>"`. Not needed in CI or on a normal PC.

**Checks of the step**

| Check | Result |
|---|---|
| Postgres healthcheck | Healthy about 5 seconds after `make up` |
| Integration test connects to the database | B3 passes |
| `make up` starts everything from scratch | Yes, on a machine with no image or volume |
| Data survives restarting the containers | B4 passes |
| No secrets in the image or the repository | B5 passes; gitleaks finds nothing in the full history (12 commits) |

### Step 1.3 Minimal CI

**Pull requests and `main`** (D-028): `.github/workflows/ci.yml`, four parallel jobs.

| Job | Steps |
|---|---|
| quality | `uv sync --frozen`, `make lint` |
| tests | `make test`, coverage report in the run summary |
| secrets | gitleaks over the whole git history |
| integration | Build `runtime` and `test` images (GitHub Actions layer cache), unit tests inside the image, `make test-integration` with the development values of `.env.example`, Postgres logs if something fails |

**Scheduled** (D-029): `.github/workflows/security.yml` every Monday at 06:00 UTC: pip-audit (also on PRs that change `uv.lock`) and Trivy on the image (HIGH and CRITICAL fail). `.github/dependabot.yml`: uv, Docker, docker compose and GitHub Actions, weekly; minor and patch grouped; major Postgres versions not proposed (D-027).

**First Trivy scan** (2026-11-22): 0 CRITICAL, 13 distinct HIGH findings, all in Debian packages of the base image. 12 have no fix in Debian yet; 1 (zlib, CVE-2026-85091) is fixed in Debian but not yet in the official Python image. All 13 are listed in `.trivyignore.yaml` with a reason and an expiry date: 2026-12-22 for the unfixed ones, 2026-12-06 for zlib (D-038). pip-audit: no known vulnerabilities.

**Supply chain** (D-030): actions pinned by commit hash, Docker images by digest, pre-commit hooks by commit hash, workflows read-only.

**Branch protection** (D-032): ruleset `protect-main`, set up by Juan on 2026-11-22 after the first CI run.

**Checks of the step**

| Check | Result |
|---|---|
| A PR with a lint error fails | Commit `345f076` added an unused import, committed with `--no-verify` to skip pre-commit on purpose. The quality job failed with ruff F401 ([run 45060339393](https://github.com/JuanGarridoGarcia/credit-risk-mlops/actions/runs/45060339393)) |
| The same PR, fixed, passes | Commit `ab6db44` removed it; all four jobs green ([run 45060408197](https://github.com/JuanGarridoGarcia/credit-risk-mlops/actions/runs/45060408197)) |
| CI takes a few minutes | 1 min 25 s on the first run and 1 min 18 s with warm caches (the integration job is the slowest; the other three take 10 to 16 s) |
| CI blocks failing PRs on `main` | Ruleset of D-032 set by Juan on 2026-11-22; the four CI jobs show as required on this PR |

### Step 1.4 Documentation skeleton

- `README.md`: showcase in nine parts (D-035).
- `docs/technical.md`: this document.
- `docs/decisions.md`: index and one card per decision (D-033); D-001 to D-018 converted with their text unchanged (checked automatically: every cell of the old table appears in the new file).
- `docs/errors.md`: index and one card per error (D-034).
- `docs/tests.md` (added in step 2.2, D-057): every test with its functions, where it runs and its change history; test B6 keeps it in step with the code.

**Check of the step**: Juan's review of this pull request.

### Clean clone

Run on 2026-11-22 in a new directory, from `git clone` to green tests:

```
git clone https://github.com/JuanGarridoGarcia/credit-risk-mlops.git && cd credit-risk-mlops
make install
make lint
make test
make build
make test-image
make test-integration
```

---

## 4. F2 Data

As in F1, every decision of F2 was explained to Juan and taken by him one at a time (2026-11-23), and every test was approved before it was written. The three decisions of the audit deferred to the simulation design were taken first: training labels from matured cohorts (D-040), first training in 2014-01 with replay to 2018-12 (D-041) and an out-of-time validation of the last 6 listing months (D-042).

### Step 2.1 Idempotent ingestion

**Flow**

```
 data/raw/accepted_2007_to_2018Q4.csv.gz         the 2019 snapshot (D-012)
        │  only the simulator reads it (D-043)
        v
 credit_risk.simulator                           plays Lending Club
        │  make publish PERIOD=YYYY-MM
        v
 data/landing/YYYY-MM/listings.csv.gz           loans listed that month (D-039)
 data/landing/YYYY-MM/outcomes.csv.gz           loans resolved that month
        │  make ingest PERIOD=YYYY-MM
        v
 raw.listings, raw.outcomes                      text as delivered (D-044)
        │  credit_risk.cleaning (D-045, D-051); validation goes here in step 2.2
        v
 clean.listings, clean.outcomes                  typed
 ops.ingest_log                                  one row per load (D-049)
```

**Delivery contract** (`credit_risk.contracts`). `listings`: the 107 columns visible at listing (audit dictionary, D-014) plus `issue_d` and `mths_since_recent_bc_dlq`, 109 in total. `outcomes`: `id` plus the 42 post-listing columns. Deliveries are gzip CSV, all text (D-050). The system depends on the contract, never on the simulator.

**Simulator** (`credit_risk.simulator`). Checks the SHA-256 of the source and its columns; drops the 33 summary rows, which sit between the 16 concatenated Lending Club files (two totals after each plus one section title), and stops on any other row that is not a loan; places each loan in its listing month and, if resolved, in its resolution month: the last payment month for good loans, last payment + 5 months for bad ones (issue + 5 if they never paid), capped at the snapshot 2019-03 (data_audit 4.2, E-013); loans still running produce no outcome; an unknown `loan_status` stops it. Rows are written in numeric id order, gzip level 6 with no timestamp, so the same input gives the same bytes. The prepared snapshot is cached as Parquet keyed by the source hash and read lazily, one month at a time (E-016). Publishing everything (2007-06 to 2019-03, 142 months, 284 files, 350 MB) takes 60 s (E-015).

**Cleaning** (`credit_risk.cleaning`, D-051). One rule per column, six kinds; the API will call the same functions on a single listing.

| Rule | Conversion | Columns |
|---|---|---|
| Integer | digits to a 64-bit integer | `id` |
| Number | text to a float; odd values such as -1, 999 or 0 stay as they are | 87 in listings, 25 in outcomes |
| Month | `Dec-2015` to 2015-12-01 | 3 in listings, 8 in outcomes |
| Term | `" 36 months"` to 36, `" 60 months"` to 60 | `term` |
| Employment length | `"< 1 year"` to 0 ... `"10+ years"` to 10 | `emp_length` |
| Flag | `Y`/`y` to true, `N`/`n` to false | `pymnt_plan`, `hardship_flag`, `debt_settlement_flag` |
| Text | unchanged, spaces included | categories, free text, statuses (16 in listings, 6 in outcomes) |

A value that does not fit stops the load with the column, the loan id and the value; a missing value stays missing. No column is removed, not even `member_id` (always empty) or `url`. Checking `annual_inc = 0` and `dti = 999` against related columns before writing the rules changed the audit's proposal (E-014): both stay as they are and go to validation.

**Postgres** (migrations in `db/migrations`, applied by dbmate from its image pinned by digest, D-048). Schemas `raw`, `clean` and `ops`. Raw and clean tables hold `period`, `load_id` and the contract columns, with `id` as primary key (a loan in two months is rejected). Deliveries are read strictly with the standard `csv` module (exact header, exact number of fields per record, E-018), then loaded with `COPY`. Each load of a period runs in one transaction: open a row in `ops.ingest_log`, delete the period, `COPY`, check rows loaded = rows in file, close the row (D-049). The same file again is logged as `unchanged`; a different one as `replaced`; a failure is rolled back and logged as `failed` with the error. Clean is always rebuilt from raw, never from the files. Ingestion requires an autocommit connection, so that each load is its own transaction and a failure record is never rolled back with it. SQL lives in `src/credit_risk/sql/`; names are composed with `psycopg.sql.Identifier`, values are always parameters (D-047).

**Commands**: `make data` (download), `make publish PERIOD=YYYY-MM`, `make migrate`, `make ingest PERIOD=YYYY-MM`, `make test-data` (tests on the real file, not in CI).

**Tests**

| Group | File | Tests |
|---|---|---|
| T1 Simulator (12) | `tests/unit/simulator/test_simulator.py`, `tests/data/test_simulator_data.py` | 1 wrong hash rejected; 2 each loan listed once, in its month; 3 listing columns exactly the dictionary's, none of the outcome; 4 outcome columns; 5 resolution month by hand (paid, bad, never paid, capped, Default, old policy); 6 running loans produce no outcome (and an unknown status stops it); 7 text unchanged; 8 identical bytes twice, no gzip timestamp; 9 summary rows dropped wherever they are, no loan lost, count reported, any other odd row stops it; 10 no outcome before its listing, nothing after the simulated date; 11 system code never imports the simulator or names the source file; 12 real file: 2,260,668 listings, 1,348,099 outcomes, 33 summary rows, snapshot 2019-03 |
| T2 Cleaning (11) | `tests/unit/test_cleaning.py`, `tests/data/test_cleaning_data.py` | 1 to 6 each rule with values that fit and values that must fail; 7 every contract column has exactly one rule; 8 the error names column, loan and value; 9 rows and order kept; 10 one row at a time equals a whole month (D-045); 11 the 284 real deliveries clean with no error and the same missing values per column |
| T3 Loading (15) | `tests/integration/test_ingest.py`, `tests/data/test_ingest_data.py` | 1 migrations up, down, up on an empty database; 2 rows and log of a load; 3 same file twice changes nothing; 4 corrected delivery replaces the month with no ghost row; 5 a failure (truncated record at the end; a primary key violation during `COPY`) leaves the month as it was and is logged; 6 deleting a month leaves the others; 7 text survives Postgres; 8 SQL injection stored as text; 9 clean equals the cleaned delivery, with Postgres types; 10 clean rebuilt from raw without the delivery file; 11 missing delivery names the file; 12 a loan in two months rejected; 13 real data: all 142 months load with the audit counts; 14 ingestion refuses a connection without autocommit; 15 real data: `COPY` faster than row-by-row `INSERT` (14 and 15 numbered in step 2.2, D-057) |

**Measurements** (2026-11-23, cloud machine, 4 CPUs)

| What | Result |
|---|---|
| Publish all deliveries | 60 s (5 min 40 s with gzip level 9, E-015) |
| Clean the 284 real deliveries | 7 s |
| Load all 142 months into raw and clean | 194 s |
| 10,000 rows of the largest month into a table | `INSERT` row by row 2.83 s, `COPY` 0.05 s (57 times faster, D-047) |
| Largest month (2016-03) | 61,992 listings |

**Checks of the step**

| Playbook criterion | Result |
|---|---|
| Any period can be loaded, reloaded or deleted with no side effects | T3.2 to T3.6, T3.12 |
| The raw data is stored as it is | T1.7, T3.7, T3.10 |
| Loading a period twice does not duplicate rows | T3.3 |
| Rows loaded equal the source | T3.2 (per load, also enforced by a check in `ops.ingest_log`), T3.13 |

### Step 2.2 Data validation

Every month is validated before it enters the clean layer. The full catalogue of rules, with the reason and the failing rows of each, is in [validation_rules.md](validation_rules.md); this section explains how it is built. Decisions D-053 to D-057; errors E-020 and E-021. Every test of the project, with its functions and its history, is in [tests.md](tests.md) (D-057).

**Flow**

```
raw (both streams) ──> strict cleaning ──> pandera rules on the typed month (in memory)
                         (formats)          + rules against history: missing values, volume
                                                     │
                                                     v
          one transaction: stage tables ──> SQL rules ──> replace the clean month
                                               │          + warnings + missing-value profile
                                               └─ a critical failure: rollback, nothing enters
```

- **The month is the unit** (D-055). `build_clean(conn, period)` cleans and validates both streams, then writes both in one transaction. A critical failure in either stream leaves the clean month as it was (or empty), records `failed` for both streams in `ops.ingest_log` with the failing rule ids, and raises `ValidationFailed` with the path of the report. Raw keeps the delivery as it arrived.
- **Levels** (D-054). Critical stops the month; a warning is reported and stored in `ops.validation_warnings` (one row per month, stream, rule and column, with up to 20 examples), replaced together with the month.
- **Dated contract** (D-056, `validation/contract.py`). The base is what was known up to 2013-12; changes C1 to C9 enter into force on their month; `contract_at(period)` builds the contract of a month. Reviewed exceptions (5 rows) pass only their rule, loan and month and are listed in every report.
- **pandera** (D-053, `validation/rules.py`). Two schemas per stream and month, critical and warning, built from the contract in force, validated in lazy mode. Every check is named by its rule id. Missing values pass every check except the required-column ones.
- **SQL** (`sql/validate_month.sql`). Both streams are copied with `COPY` into temporary stage tables (`CREATE TEMP TABLE ... (LIKE clean.x) ON COMMIT DROP`) inside the load transaction; one query returns every failing value of R1.3, R1.5, R1.6, R2.13, R3.11, R3.12 and R3.15 against the clean history plus the stage. Only if nothing critical fails is the month moved from the stage into clean.
- **History rules** (`validation/report.py`). R4.6 compares the missing-value share of each column with the previous month's profile, stored in `ops.column_profile` on every load. R5 compares the volume with the median of the 12 previous live clean loads in `ops.ingest_log`; it is not applied with fewer than 12 months or a median below 1,000 (R5.3), and the report says so.
- **Cleaning** now reports every failing column of a month at once (`CleaningError.failures`), as pandera does.
- **Report** (D-053). Every run writes `validation/<YYYY-MM>/validation_<timestamp>.json` and a `.md` summary next to the landing folder (`data/validation`): status, rows per stream, contract changes in force, every finding with rule, level, stream, column, count and examples, and notes on rules not applied.

**Postgres**: new migration `20261123130000_create_validation_tables.sql` with `ops.validation_warnings` and `ops.column_profile` (both with checks on period, stream and counts, and a foreign key to the load). `delete_period` also removes them.

**Commands**: unchanged. `make ingest PERIOD=YYYY-MM` now validates; a failure exits with the report path.

**Tests**

| Group | File | Tests |
|---|---|---|
| T4 Validation (16) | `tests/unit/test_validation.py`, `tests/integration/test_validation.py`, `tests/data/test_ingest_data.py`, `tests/data/test_validation_data.py` | 1 a valid month passes every rule; 2 each critical pandera rule fails on a valid row with one change and names itself, the loan and the value (36 cases, and a check that every rule has one); 3 each warning lets the month pass and is counted (7 cases); 4 three broken rules reported at once; 5 limits inclusive (amount, rate, money tolerance, FICO, `dti`, volume ratios and the 1,000 minimum, missing-share 10 points); 6 each dated change fails the month before and passes from its month (C1 to C9); 7 reviewed exceptions pass only their rule, loan and month; 8 cleaning reports every failing column; 9 every rule in the code is in the catalogue and back; 10 each SQL and history rule has a failing case in Postgres; 11 a critical failure stops the whole month and rolls back a failing SQL rule; 12 warnings stored once per month; 13 a failed month enters once fixed; 14 every run writes its JSON and summary report; 15 real data: no critical failure, the 5 exceptions, and every warning count and month of the catalogue; 16 real data: the base contract alone stops exactly at the months of C1 to C9 |

Tests T3 were kept as approved; their fixtures now start from rows that pass validation (`tests/valid_rows.py`) and `build_clean` builds a month instead of one stream, because the month became the unit.

**Measurements** (2026-11-23, cloud machine, 4 CPUs)

| What | Result |
|---|---|
| pandera rules over the 284 real deliveries | 28 s listings, 10 s outcomes |
| Load all 142 months into raw and clean, with validation | 383 s (194 s without validation in step 2.1) |
| Full real load | 0 critical failures; 5 reviewed exceptions; warnings: R2.10 2,563 rows, R2.11 3, R2.12 20, R2.13 21 months, R3.14 4, R3.15 433, R4.6 153 column-months (4 months in 2014 to 2018), R5.2 4 months |
| Application image | 466 MB (pandera adds 10 MB; budget 500 MB, D-052) |

**Checks of the step**

| Playbook criterion | Result |
|---|---|
| Every run validates the data and a critical failure stops the pipeline | T4.2, T4.10, T4.11 |
| Rules are explicit, with level and reason | `docs/validation_rules.md`; T4.9 keeps code and catalogue equal |
| Each failure says what, where and why | T4.2, T4.14 |
| Warnings are kept for monitoring | T4.12 |
| The rules hold on the real data | T4.15, T4.16 |

### Step 2.3 Data versioning

A model must be reproducible months later, but `clean` changes when a corrected delivery replaces a month (D-049). So the training set at a cutoff month T is built once and kept as an immutable version. Decisions D-058 to D-061; error E-022.

**Flow**

```
clean (every month up to T, checked) ──SQL──> loans of the set at T ──COPY──> two frames
                                               matured, labelled, split        features / evaluation
                                                                                     │
                       content hash of the data (the name of the version) <──────────┘
                                     │
           new: write both Parquet files to training_sets/<hash>/, then the manifest
           known: write nothing, check the stored files against their checksums
```

- **The set at T** (`sql/training_ids.sql`). Matured cohorts: listed at least `term + 5` months before T (D-040). The label comes only from outcomes delivered by T: Fully Paid 0, Charged Off and Default 1 (D-013); old-policy loans and matured loans with no outcome yet are left out and counted. Validation is taken per term (D-069, which replaced D-042 in F3): the last 6 matured listing months of each term, 36-month loans listed T-46 to T-41 and 60-month loans T-70 to T-65; earlier matured loans are training. The LGD label `lgd` (D-088) is computed here: `(funded - principal repaid - (recoveries - collection fee)) / funded`, only for bad loans resolved at least 12 months before T (D-017), empty for every other loan.
- **Before anything**, every month and stream from 2007-06 to T must have a live clean load whose last attempt did not fail; otherwise the build stops and names the months.
- **Two files** (D-060). `features.parquet`: every column of `clean.listings`, `label`, `lgd` (since F3) and `split`, with the types of the cleaning rules. `evaluation.parquet`: the outcome columns of the same loans and the month each was resolved. Training reads only the first.
- **Two hashes** (D-061, `snapshot.content_hash`). The content hash is SHA-256 over the data in one fixed text form (rows sorted by `id`, column names and types, floats with 17 significant digits, text always quoted, missing values marked apart), so it changes only when the data change. The checksum of each file goes in the manifest and is checked on every read and rebuild.
- **Store** (D-059, `storage.py`). A version is the folder `data/training_sets/<hash>/`, filled under a temporary name and renamed in one step; it is never overwritten. The S3 store comes with the AWS phase behind the same interface.
- **Manifest** (D-058). `ops.training_sets`: version, cutoff, git commit (`-dirty` if the tree has changes; `CREDIT_RISK_COMMIT` in an image), path, counts, exclusions, checksums. `ops.training_set_loads`: the clean load of every month and stream used. `python -m credit_risk.snapshot stale` lists the versions built on a load that has since been replaced.
- **One consistent view**: the build runs in one `REPEATABLE READ` transaction, so clean cannot change halfway.

**Postgres**: new migration `20261123150000_create_training_sets.sql` with `ops.training_sets` and `ops.training_set_loads` (foreign keys to `ops.ingest_log`).

**Commands**: `make snapshot T=YYYY-MM` builds the version at T and prints its hash.

**Tests**

| Group | File | Tests |
|---|---|---|
| T5 Training set versions (14) | `tests/unit/test_snapshot.py`, `tests/integration/test_snapshot.py`, `tests/data/test_snapshot_data.py` | 1 maturity at 41 and 65 months; 2 label and old policy; 3 outcome unknown at T left out; 4 last 6 months are validation; 5 no outcome column in the training file; 6 a missing or failed month stops the build; 7 manifest; 8 content hash follows the data, not the file; 9 a rebuild writes nothing; 10 a corrected month gives a new version and flags the old; 11 a changed file is refused; 12 SQL equals an independent polars version on 2,000 random loans; 13 and 14 real data at T0 |

Every test, with its functions, is in [tests.md](tests.md). The SQL was also checked by mutation: moving the maturity by one month, reading outcomes after T, a 7-month validation window or another label mapping each make T5 tests fail. In F3 (2026-11-24) the same check for the new rules: a 7-month window, a window taken from the 36-month term for both terms, an LGD age of 11 months, or recoveries without the collection fee each make T5 tests fail.

**Measurements** (2026-11-23, cloud machine, 4 CPUs; all 142 months in clean)

| Cutoff | Train (defaults) | Validation (defaults) | Old policy left out | No outcome yet | Build | Size |
|---|---|---|---|---|---|---|
| 2014-01 (T0) | 7,733 (1,019) | 4,324 (429) | 2,226 | 25 | 1.3 s | 2.6 MB |
| 2016-01 | 34,613 (4,089) | 19,060 (2,700) | 2,587 | 9 | 2.6 s | 8.2 MB |
| 2018-12 | 394,952 (56,404) | 127,952 (19,208) | 2,749 | 80 | 13.2 s | 67 MB |

**Measurements after F3's split per term and LGD label** (2026-11-24, same machine; full load 371 s). By term: 36 / 60 months.

| Cutoff | Train (defaults) | Validation (defaults) | With `lgd` (train / validation) | Mean `lgd` | Build | Size |
|---|---|---|---|---|---|---|
| 2014-01 (T0) | 7,733 (1,019): 36 only | 4,324 (429): 36 only | 992 / 344 | 0.605 | 1.4 s | 2.6 MB |
| 2016-01 | 33,237 (3,795): 36 only | 20,436 (2,994): 19,060 (2,700) / 1,376 (294) | 3,731 / 2,509 | 0.589 | 2.5 s | 8.5 MB |
| 2018-12 | 381,111 (52,877): 359,189 (47,339) / 21,922 (5,538) | 141,793 (22,735): 127,952 (19,208) / 13,841 (3,527) | 52,163 / 19,450 | 0.551 | 12.7 s | 70 MB |

T0 is unchanged: no 60-month loan is matured then. At 2016-01 every matured 60-month loan falls in validation (the first ones were listed in 2010-05, inside the window T-70 to T-65), so 60-month loans have no training loan yet and stay out of coverage (D-070) until a cutoff of about 2016-04. Mean `lgd` falls with later cutoffs; the reason is studied with the LGD model (second F3 pull request).

The version at T0 built from a database loaded only up to 2014-01 (data test) and from one loaded with all 142 months has the same hash: the build never reads past T. A rebuild at 2018-12 with no change takes 13.0 s and writes nothing. The audit's 12,078 loans at T0 included 21 resolved after T0 (E-022).

**Checks of the step**

| Playbook criterion | Result |
|---|---|
| Any training set can be rebuilt exactly | T5.8, T5.9; same hash from two independent loads |
| A version records where it came from | T5.7 |
| Changes in the data are detected, not silently absorbed | T5.10, T5.11 |
| No information from after T, no leakage into training | T5.3, T5.5, T5.12 |

### Step 2.4 Features

The model receives 30 features computed by `credit_risk.features.build_features`, the same function in training, in the API (F5) and in monitoring (F6). Decisions D-062 and D-063.

**Two layers** (D-062)

```
cleaned listing(s) ──> build_features (fixed, no state) ──> model pipeline (F3)
                       id + 30 features, gaps kept          learned: fill gaps, encode,
                                                            scale; fitted on train only
```

- **Fixed layer** (`features.py`): pure polars expressions on each row; nothing depends on other rows, so one listing and a whole month give the same values (T6.6).
- **Learned layer** (F3): inside the model pipeline, fitted on the training split of a version (step 2.3) and saved with the model.

**v1 features** (D-063). 20 listing columns used as they are, the FICO midpoint, the credit history in months, and 8 categorical columns. Left out: `installment` (funded-amount leak, decided in F3), `pub_rec_bankruptcies` (filled only from 2009, D-016), free text (D-015), state and zip code (D-018), the bureau fields reported from 2012 and 2015 and the second-applicant fields (D-016). Engineered features (ratios, logarithms, `sub_grade` as a number) are F3 experiments, each kept only if it beats the metric noise.

Checked on the real deliveries before writing the code: the credit history goes from 6 to 999 months and is never negative; `fico_range_high` is `fico_range_low` + 4 in 2,260,227 loans and + 5 in 441.

**Tests**

| Group | File | Tests |
|---|---|---|
| T6 Features (8) | `tests/unit/test_features.py`, `tests/data/test_features_data.py` | 1 credit history by hand; 2 FICO midpoint by hand; 3 `id` and the 30 features with their types; 4 no forbidden column reaches the output; 5 every source visible at listing and reported since 2007; 6 one row equals a whole month in any order; 7 no gap filled; 8 real data: the version at 2018-12 in range |

The full real load of the data tests now runs once per session (`tests/data/conftest.py`) and is shared by T3.13, T3.15, T4.15 and T6.8.

**Checks of the step**

| Playbook criterion | Result |
|---|---|
| Features are computed the same way in training and serving | One function for both; T6.6 |
| No feature uses information from after the listing | T6.4, T6.5; outcomes live in another file of the version (D-060, T5.5) |
| What is learned is fitted on training data only | By design (D-062): nothing learned in `features.py`; T6.7 |

### F2 cross-cutting: coverage minimum

D-064 closes D-031. `make test-integration` runs the unit tests and the non-destructive integration tests under one coverage measurement and fails below 85% of branches; `make diff-cover` fails when less than 90% of the lines changed against `origin/main` are covered. Both run in the CI integration job, which also writes the two reports to the run summary. Measured on 2026-11-23: unit tests alone 58%, unit and integration 89%.

### F2 cross-cutting: the audit notebook in CI

D-065 closes the open point of D-021. `make notebooks` runs `notebooks/00_data_audit.ipynb` top to bottom with nbconvert and fails if any file of `reports/data_audit` differs from the committed one: byte for byte with `git diff --exit-code`, except the PNG figures (E-024): a figure only draws a table that is compared, such as `loans_per_month.csv`. The notebook resets matplotlib to its built-in defaults, so a figure does not depend on the machine's settings. A failed run keeps its outputs as a workflow artifact for 14 days. The `Notebooks` workflow runs it every Monday at 05:00 UTC, by hand, and on pull requests that touch the notebook, its outputs, `uv.lock` or the workflow, with the secret `KAGGLE_API_TOKEN`, which must exist twice: as an Actions secret and as a Dependabot secret, because workflows started by Dependabot only see Dependabot secrets (E-026). Run here on 2026-11-23: 1 min 53 s, every output byte-identical.

---

## 5. F3 Model

Every decision of F3 was explained to Juan and taken by him one at a time (2026-11-23 and 2026-11-24), D-066 to D-089. F3 is delivered in three pull requests (D-089): data, training, explanation and business.

**The design in one page**

| Topic | Decision |
|---|---|
| What F3 fixes | A training procedure, not a model, designed with the T0 snapshot only (D-067) |
| Split | Validation per term: the last 6 matured months of each term (D-069, replaces D-042) |
| Terms not yet seen | A term is scored only with at least 200 defaults in its training and 200 in its validation (D-070) |
| PD candidates | Regularised logistic regression and LightGBM; within the noise the simpler wins (D-068, D-072) |
| Features | The 30 v1 inputs; `installment` never; recomputed instalment and instalment to income as experiments (D-071) |
| Tuning | On an inner time split of the training set; Optuna TPE with 50 seeded trials for LightGBM, a grid over `C` for the logistic regression (D-073, D-074) |
| Better than another model | 95% paired bootstrap interval of the difference above zero (D-075) |
| Calibration | Platt scaling fitted on validation; no refit on training plus validation (D-076, D-077) |
| Images | `serve` (800 MB) and `train` (1.5 GB) from one Dockerfile (D-078) |
| Tracking | MLflow server in compose, metadata in Postgres, artefacts in object storage (D-079) |
| Model tests | Monotone constraints and signs (D-080); key segments (D-081); behavioural battery (D-086) |
| Promotion | Automatic when every rule passes, with evidence, alert and tested rollback (D-082) |
| Explanations | Four main reasons in the API; full SHAP vector stored (D-083) |
| LGD | Linear and LightGBM against the mean by grade, same machinery (D-087); label computed in the snapshot (D-088) |
| Buy rule | Expected return above a minimum chosen on validation; 25 dollar notes, monthly cap of 10% of last month's listings (D-084, D-085) |

### First pull request: data

The two changes to the training set that training depends on, in `sql/training_ids.sql`: the validation split per term (D-069) and the LGD label `lgd` in `features.parquet` (D-088). Both are described with step 2.3, where they live, together with their measurements on the real data. Tests: T5.4, T5.5, T5.12 and T5.13 changed, T5.15 added (approved by Juan on 2026-11-24).

### Second pull request: training

Tests approved by Juan before any code is written. They enter `docs/tests.md` with their code, because B6 fails on a catalogue row whose function does not exist yet; until then this list is the record of what was approved.

**T7 Training** (approved 2026-11-24)

| ID | What it checks |
|---|---|
| T7.1 | Learned preparation sees training only (D-062): the fill value of `dti` and the known categories of `purpose` equal what is computed by hand on training; extreme values in validation change nothing |
| T7.2 | An odd row does not break prediction: an unseen category, every field empty and extreme values give a finite probability between 0 and 1, for both candidates |
| T7.3 | The inner split for tuning (D-073) is the last 6 matured months of each term inside training, edges tested as in T5.4; the search never receives a validation id (every id used to fit or score a trial is recorded and checked) |
| T7.4 | Same seed, same result (D-074): two trainings give the same hyperparameters and predictions; the budget is counted, 50 trials for LightGBM and 20 values of `C` for the logistic regression |
| T7.5 | Coverage rule (D-070): 200 defaults in training and 200 in validation is covered; 199 in either is not; a loan of an uncovered term gets "not covered", never a PD |

**T8 Tracking** (approved 2026-11-24)

| ID | What it checks |
|---|---|
| T8.1 | The MLflow server starts in compose and answers; its metadata are in the `mlflow` database of our Postgres, not in a file inside the container |
| T8.2 | A run with a small artefact survives recreating the MLflow container. Marked `destructive`, like B4 |
| T8.3 | No run without its required fields: one function logs every run and refuses, naming the field, if the commit, snapshot hash, seed, library versions or metrics with intervals are missing (one case per field); a small real training read back from the server carries all of them |
| T8.4 | The model is rebuilt from what a run records (snapshot version, seed, hyperparameters) and gives the same predictions as the stored model |

**T9 Model comparison** (approved 2026-11-24)

| ID | What it checks |
|---|---|
| T9.1 | The paired bootstrap (D-075) on cases with a known answer: a clearly better model wins, an identical one does not (difference zero in every resample), a clearly worse one loses; every resample keeps the number of defaults; same seed, same interval; the sign is reversed for a metric where lower is better (Brier) |
| T9.2 | The choice rule (D-068): LightGBM is chosen only if its interval against the logistic regression lies entirely above zero; if it touches zero the logistic regression wins, even with a higher mean AUC |
| T9.3 | The segments (D-081): F and G merged, covered terms only, quarters of validation; a segment with 49 defaults is merged with its neighbour and one with 50 is not; a model better overall but clearly worse in grade A fails; a tie in a segment passes |
| T9.4 | The signs (D-080): the nine coefficients of the logistic regression have the expected sign, and made-up data where a higher `int_rate` lowers risk make the check fail; LightGBM is trained with exactly the fixed list of constraints, logged in the run |

**T10 Behaviour** (approved 2026-11-24). The battery (D-086) is a function run on every model before promotion (D-082); these tests check that it does its job.

| ID | What it checks |
|---|---|
| T10.1 | Invariance: changing fields the model does not use (`id`, `emp_title`, `addr_state`) leaves the PD unchanged; a loan scored alone or in a batch gets exactly the same PD |
| T10.2 | Direction: on real validation loans, raising each of the nine features of D-080 in its risk direction never lowers the PD, and the reverse for the protective ones |
| T10.3 | Minimum cases: a clearly good profile (grade A, FICO 800, `dti` 5, no delinquencies) gets a lower PD than a clearly bad one; every PD is between 0 and 1; empty optional fields are scored without error; an uncovered term gets no PD |
| T10.4 | Time: one prediction takes under 50 ms (p95) in process. Measured without the explanation here; extending it to include SHAP in the third pull request needs Juan's approval |
| T10.5 | Bad models fail: a constant model and a random model fail the battery |
| T10.6 | Data test: the model trained at T0 on the real data passes the whole battery |

**T11 Registry** (approved 2026-11-24). Integration tests against the MLflow of compose.

| ID | What it checks |
|---|---|
| T11.1 | Only a challenger that passes every rule is promoted: the alias `champion` moves to it; one case per rule where only that rule fails (noise, a segment, a sign, the battery) leaves the alias where it was; the promotion function has no option to skip a rule |
| T11.2 | Every decision leaves evidence in the challenger's run, promoted or not: intervals, segments, battery results and, if rejected, the reason. Small values as tags and metrics (Postgres), the 1,000 differences, segment table and battery report as artefacts |
| T11.3 | Every promotion alerts: until Grafana (F6), a WARNING log message with the previous and new champion, plus a tag in MLflow |
| T11.4 | Rollback in one command (`make rollback MODEL=pd`): the alias returns to the previous champion, read from the tag written on each promoted version; predictions are again exactly those of that model; the rollback leaves evidence and alerts; with no previous champion it fails clearly and changes nothing |
| T11.5 | The first champion (D-090): with no champion, the chosen model is compared with the grade-only baseline under the same rules; if it does not beat it, the baseline is the champion |

**Images** (approved 2026-11-24), in group B where the image already lives.

| ID | What it checks |
|---|---|
| B5 (changed) | Both images, each against its own budget: `serve` at most 800 MB, `train` at most 1.5 GB (D-078); the rest of B5 (non-root, no `.env`, no secrets, right version) applies to both. If the measured images do not fit, the budgets go back to Juan first |
| B7 | `serve` carries nothing of training: importing Optuna, SHAP or the full MLflow server fails inside it |
| B8 | A small model trained in `train`, saved and loaded in `serve` gives identical predictions |
