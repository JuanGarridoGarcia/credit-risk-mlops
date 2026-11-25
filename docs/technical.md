# Technical document

The full detail of the project, one section per step of the playbook: what was built, how, which numbers came out, which decisions and errors happened, and how it was checked. The README is the short version; this is the manual. Format decided in D-035.

Related documents: [problem definition](problem.md), [data audit](data_audit.md), [decision log](decisions.md), [error log](errors.md), [validation rules](validation_rules.md), [test catalogue](tests.md).

## Contents

1. Tracking sheet
2. F0 Framing (steps 0.1, 0.2)
3. F1 Foundations (steps 1.1 to 1.4)
4. F2 Data (steps 2.1 to 2.4)
5. F3 Model (steps 3.1 to 3.5)
6. F4 Automation (step 4.1)
7. F5 Deployment (step 5.1 and old step 4.2; step 5.2 to come)

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
| F3 Model | 3.1 Baseline | Done | #7, PR 2 | D-067, D-069, D-070, D-090. Split per term (D-069) in the data PR; grade-only baselines for PD and LGD in PR 2 |
| | 3.2 Tracking and experiments | Done | #7, PR 2 | D-068, D-071 to D-079, D-087, D-088, D-091, D-092, D-094; E-027 to E-036 |
| | 3.3 Model tests and promotion rules | Done | PR 2 | D-080, D-081, D-086, D-093 |
| | 3.4 Model registry | Done | PR 2 | D-082, D-090 |
| | 3.5 Explainability and model card | Done | PR 3 | D-083, D-095; buy rule, budget and business result D-084, D-085, D-096, D-097 |
| F4 Automation | 4.1 Orchestrated training flow | Done | #10, #11 | D-098 to D-108; E-037 to E-042; #11: clock, cadence and alerts |
| | 4.2 Batch prediction flow | Done (in F5) | #13 | Replaced by the simulated investor calling the API (D-008, D-098); D-123 to D-129; E-047 |
| F5 Deployment | 5.1 API | Done | #12 | D-109 to D-122; E-043 to E-046; API, predictions table, buy rule in MLflow; purchases endpoint in PR 2 (D-124) |
| | 5.2 Published image and CD | In review | PR 3 of F5 | D-130 to D-136; E-048; serve and train published to GHCR after CI on main, smoke tested, Trivy before publishing |
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
| LGD | Linear and LightGBM against the mean by grade, same machinery (D-087); label computed in the snapshot (D-088); level corrected on validation (D-094) |
| Buy rule | Expected return above a minimum chosen on validation; 25 dollar notes, monthly cap of 10% of last month's listings (D-084, D-085) |

### First pull request: data

The two changes to the training set that training depends on, in `sql/training_ids.sql`: the validation split per term (D-069) and the LGD label `lgd` in `features.parquet` (D-088). Both are described with step 2.3, where they live, together with their measurements on the real data. Tests: T5.4, T5.5, T5.12 and T5.13 changed, T5.15 added (approved by Juan on 2026-11-24).

### Second pull request: training

Tests approved by Juan before any code was written (2026-11-24). They are now catalogued, with their functions, in [tests.md](tests.md); the tables below are the wording he approved.

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
| T9.3 | The segments (D-081): F and G merged, covered terms only, quarters of validation; a segment with 49 defaults is merged with its neighbour and one with 50 is not; a model better overall but clearly worse in grade A fails; a tie in a segment passes; clearly worse but within the margin of D-093 passes (case added 2026-11-24, approved by Juan) |
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

**T12 LGD** (approved 2026-11-24)

| ID | What it checks |
|---|---|
| T12.1 | Only defaults with a known LGD enter: training and validation use only the rows with `lgd` of their split; good loans, unresolved loans and charge-offs younger than 12 months never enter (ids recorded, as in T7.3) |
| T12.2 | The baseline: the mean by grade equals the one computed by hand on training and is applied as it is to validation |
| T12.3 | The baseline can win: with made-up data where LGD is pure noise no candidate beats the mean by grade on RMSE with the paired bootstrap, and the baseline is the champion; with data where LGD clearly depends on a feature, the candidate wins |
| T12.4 | The level by segment rules: a candidate with a good RMSE but a clearly wrong mean LGD in one grade fails the segment rule of D-081 |
| T12.5 | Always between 0 and 1: extreme inputs give a prediction in [0, 1] (the label can fall outside, as the -0.6 of T5.15, and the linear regression extrapolates) |
| T12.6 | Data test at T0: trained on the 992 training rows and validated on the 344; logs the RMSE, the interval against the baseline and the champion; fixes no winner, but the mean predicted LGD in validation lies inside the interval of the observed mean |
| T12.6 (changed 2026-11-24, D-094) | Data test at T0: as above, with the level corrected on validation; logs the shift of each model and the gap before the correction; the champion's mean predicted LGD in validation is within 0.005 of the observed mean, and no shift exceeds 0.10 |
| T12.7 (added 2026-11-24, D-094) | The level correction on made-up data whose validation LGD is 0.10 above training: shift by hand, set by validation only, order unchanged, predictions in [0, 1], one shift per model, the baseline included |

#### How training works

```
training set version (features.parquet, T)
   |
   |  prepare_frame: the 30 fixed features + issue_d, label, lgd, split
   v
train_pd ------------------------------------------- train_lgd (defaults with lgd only)
   inner split of training (D-073)                      ridge over 20 alphas, LightGBM 50 trials
   logistic: 20 values of C, signs checked (D-092)      baseline: mean LGD by grade
   LightGBM: 50 Optuna trials, monotone (D-080)         level corrected on validation (D-094)
   Platt scaling on validation (D-076)                  chosen by RMSE with the paired bootstrap
   chosen: LightGBM only if clearly better (D-068)
   |                                                    |
   v                                                    v
log_run: one MLflow run per model, refused without commit, snapshot, seed,
         library versions or metric intervals (D-079)
   |
   v
register the chosen model as a new version of "pd" / "lgd"
   |
   v
promote: noise, segments (with margins, D-093), signs, battery (PD only)
   pass -> alias "champion" moves, WARNING alert, previous champion written on the version
   fail -> the champion stays; the reasons and the evidence stay in the run
```

| Module | Role |
|---|---|
| `model.py` | Learned preparation (`Prepare`), the PD and LGD model classes, coverage rule (D-070), signs and constraints (D-080) |
| `train.py` | The PD procedure: inner split, searches, Platt scaling, choice |
| `lgd.py` | The LGD procedure on the same machinery |
| `compare.py` | Metrics, paired bootstrap (D-075), segments and their margins (D-081, D-093) |
| `battery.py` | The behavioural battery (D-086) |
| `explain.py` | The explanation of each PD: base value, one contribution per feature, the four main reasons (D-083); global importance |
| `card.py` | The model card of every registered version (D-095) |
| `business.py` | Buy rule, budget, choice of the minimum and realised return (D-084, D-085, D-096) |
| `tracking.py` | Run records and their check (D-079); the MLflow server of compose |
| `registry.py` | Storing, registering, promotion, alert and rollback (D-082, D-090) |
| `pipeline.py` | `make train T=YYYY-MM`: the newest training set version at T, both targets, register and promote |

| Command | What it does |
|---|---|
| `make train T=2014-01` | Trains the PD and the LGD on the newest training set version at T, logs every model in MLflow, registers the chosen ones and tries to promote them |
| `make rollback MODEL=pd` | Puts back the champion before the current one (D-090); fails clearly if there is none |
| `python -m credit_risk.registry champion pd` | Prints the version of the current champion |

**MLflow** (D-079, D-091). The server runs in compose from our own `train` image (`python -m credit_risk.tracking server`), with its metadata in a database `mlflow` of our Postgres (created on start if missing) and its artefacts in the named volume `mlartifacts`, served through the server (`--serve-artifacts`), so a client never needs the volume. UI at http://localhost:5000. A model is stored as `model/model.joblib` in the artefacts of its run and registered under `pd` or `lgd`; the alias `champion` names the model in use. Each promoted version carries the tags `previous_champion` and `promoted_at`; each decision writes on the challenger's run the tags `promotion.outcome`, `promotion.reasons` and `rule.<rule>`, the metrics `promotion.*`, and the artefact `promotion/evidence.json` (the 1,000 bootstrap differences, the segment table, the battery report).

**Images** (D-078). Built by `make build` from one Dockerfile:

| Image | Target | Content | Size (sum of layers, 2026-11-24) | Budget |
|---|---|---|---|---|
| `credit-risk:serve` | `serve` | The package with the main dependencies: polars, scikit-learn, LightGBM, mlflow-skinny | 752 MB | 800 MB |
| `credit-risk:train` | `train` | The same plus the group `train`: full MLflow (server), Optuna, SHAP | 1,229 MB | 1,500 MB |

Both share the `runtime` base, which adds the OpenMP runtime LightGBM needs (`libgomp1`, E-027). B7 checks that nothing of training reaches `serve`; B8 trains a model in `train`, registers it in MLflow and loads it in `serve` with the same predictions.

**Measured at T0 = 2014-01** (real data, first training set version; 36-month loans only):

| | Value |
|---|---|
| Training / validation | 7,733 loans (1,019 defaults) / 4,324 loans (429 defaults) |
| PD, validation AUC | logistic regression 0.677, LightGBM 0.680, baseline (grade) 0.636 |
| PD, LightGBM against logistic | AUC difference interval [-0.013, +0.020]: touches zero, so the logistic regression is chosen (D-068) |
| PD, AUC interval width | about ±0.014, as estimated when the 200-default minimum was fixed (D-070) |
| PD, logistic regression signs | `pub_rec` and credit history came out with the wrong sign and were removed (D-092) |
| PD, promotion | The logistic regression beats the baseline on every rule and becomes the first champion (D-090, D-093) |
| LGD, level before the correction | every model about 5 points too low: mean predicted 0.592 against 0.642 observed, interval [0.620, 0.664]; the LGD rises with the listing year, 0.50 (2007) to 0.64 (2010) |
| LGD, level correction (D-094) | ridge +0.050, LightGBM +0.054, baseline +0.050 |
| LGD, validation RMSE | before the correction: ridge 0.2216, LightGBM 0.2241, baseline 0.2214; after: 0.2157, 0.2176, 0.2156 |
| LGD, promotion | No candidate beats the baseline: the mean LGD by grade is the champion (D-087) |
| Whole retrain (both targets, every search, MLflow) | about 40 seconds |

### Third pull request: explanations and business

Tests approved by Juan before any code was written; catalogued in [tests.md](tests.md).

**T13 Explanations** (approved 2026-11-24)

| ID | What it checks |
|---|---|
| T13.1 | Additivity for the logistic regression, LightGBM and the baseline: base value plus contributions equals the log-odds of the calibrated PD (relative and absolute tolerance 1e-9), on validation loans and odd rows (every optional field empty, an unseen category, extreme values) |
| T13.2 | They are real SHAP values: our contributions equal those of the `shap` library (`LinearExplainer` with the training rows as background, `TreeExplainer`) within 1e-6. Runs where `shap` is installed (CI, the test and train images), never in `serve` |
| T13.3 | One contribution per original feature: one-hot columns and "was missing" columns are summed into their feature; the vector has exactly the 30 features; a feature the model does not use contributes 0 (the baseline: everything but the grade) |
| T13.4 | The four main reasons are the four largest contributions in absolute value, with their sign and the feature's value; ties keep the order of the features; a case by hand. A loan with no PD gets no reasons, and a feature with no contribution is no reason |
| T13.5 | The reasons make sense: for the clearly bad profile of the battery the main reason raises the PD, for the clearly good one it lowers it, for both candidates |
| T10.4 (changed) | One prediction **with** its explanation takes under 50 ms (p95) |

#### How explanations work

Each PD is explained as a base value plus one contribution per feature, in log-odds, computed without the `shap` library so that `serve` stays light (D-078, B7):

| Model | Contribution of a column | Base value |
|---|---|---|
| Logistic regression, baseline | coefficient x (value - its mean on training) | intercept + coefficients x training means |
| LightGBM | LightGBM's own `pred_contrib` (the tree algorithm of `shap.TreeExplainer`) | the last column of `pred_contrib` |

Then Platt scaling (`a x raw + b`) multiplies every contribution by `a` and turns the base into `a x base + b`. The columns made from one feature (one-hot categories, the "was missing" column) are summed into that feature, so every explanation has the same 30 features and a feature the model does not use contributes 0. The four main reasons are the four largest contributions in absolute value; ties keep the order of the features, and a zero contribution is never a reason. For LightGBM the raw log-odds of the PD are now read directly from the model (`raw_score`), the exact sum of its contributions, instead of the log-odds of its probability.

**T14 Model card** (approved 2026-11-24)

| ID | What it checks |
|---|---|
| T14.1 | Every registered version has its `model_card.md` in the artefacts of its run, champion or not (the chosen model and the baseline of each target), with every section in order |
| T14.2 | A card missing any of its sections is refused, naming the section |
| T14.3 | The numbers of the card are those of the run: metrics with intervals, training set version, run, and the counts of loans and defaults, which also match a count by hand |
| T14.4 | The global importance is the mean absolute contribution on validation, by hand on a small case (covered terms only), largest first |
| T14.5 | Each card carries what is particular to its model: the features removed by D-092 for the PD, the level shift of D-094 for the LGD |
| T14.6 | Data test: the cards in `docs/model_cards/` are those of the T0 champions, generated by the same function (title, run and commit aside) |

#### Model cards

Every version registered by `make train` gets a `model_card.md` in its run (D-095), built by `credit_risk.card` from what the run recorded and from the stored model: the model and its training set, intended and not intended uses, counts, metrics with intervals, the promotion verdict, segments, battery, global importance (mean absolute SHAP contribution on validation), features left out on purpose and known limits. The runs now also record the counts of loans and defaults of each split (`rows.*`, `defaults.*`). The cards of the T0 champions are in [`docs/model_cards/`](model_cards/): the logistic regression for the PD and the grade-only baseline for the LGD.

**T15 Buy rule and business metric** (approved 2026-11-24)

| ID | What it checks |
|---|---|
| T15.1 | Scheduled interest with the amortisation formula, by hand: 36 months at 7% gives 0.111 and at 20% gives 0.338 (the examples of D-084); a rate of 0% gives 0 |
| T15.2 | Expected return = (1 - PD) x scheduled interest - PD x LGD, by hand on the two examples of D-084 (0.083 and 0.103); a loan with no PD (term not covered) is never bought |
| T15.3 | Budget (D-085): K is 10% of the loans listed the month before, rounded down; loans that pass are bought in listing order until K and the rest are skipped; one 25 dollar note per loan |
| T15.4 | Realised return by hand: a paid loan, a defaulted one with recoveries and collection fee, and idle money counted as zero; return = (received - invested) / budget |
| T15.5 | The minimum is chosen on validation only, from a fixed grid, as the one with the highest realised return under the same budget (a tie goes to the smallest); the ids used are recorded |
| T15.6 | On made-up data where our PD is informative and the baseline's is not, our investor earns more with exactly the same budget every month |
| T15.7 | Data test (D-096): the T0 champions against the baseline on the loans listed from 2014-02 to 2015-01, with their final outcomes; records realised default rate, loss and net return at caps of 5%, 10% and 20%; fixes no winner; checks the same budget, that everything bought is covered and listed in that year, and that nothing of that year chose the minimum |

#### Buy rule and business metric

`credit_risk.business` (D-084, D-085, D-096). For each loan, scheduled interest from `int_rate` and `term` (amortisation), expected return `(1 - PD) x scheduled interest - PD x LGD`. Each month at most K notes of 25 dollars, K = 10% of the loans listed the month before; loans with an expected return at or above the minimum are bought in listing order (the order of their ids) until K. A note receives its share of `total_pymnt` less the collection fee; the net return is (received - invested) over the money available, so idle money counts as zero. It is the total over the life of the loans, not annualised (all are 36-month loans). The minimum is chosen from a grid from -0.10 to 0.30 in steps of 0.005, on validation only; the realised return is measured on the loans listed in the 12 months after T0.

Measured at T0 by T15.7 (2026-11-24), loans listed from 2014-02 to 2015-01, same budget for both investors every month:

| Cap | Investor | Minimum | Notes | Budget ($) | Default rate | Loss | Net return |
|---|---|---|---|---|---|---|---|
| 5% | model | +0.145 | 11,478 | 294,375 | 0.198 | 0.076 | +0.0899 |
| 5% | baseline | +0.105 | 11,775 | 294,375 | 0.176 | 0.067 | +0.0895 |
| 10% | model | +0.135 | 21,301 | 588,900 | 0.186 | 0.071 | +0.0846 |
| 10% | baseline | +0.105 | 23,556 | 588,900 | 0.177 | 0.067 | +0.0895 |
| 20% | model | +0.120 | 37,656 | 1,177,975 | 0.173 | 0.065 | +0.0749 |
| 20% | baseline | +0.100 | 45,942 | 1,177,975 | 0.166 | 0.063 | +0.0870 |

At T0 our model does not beat the grade baseline on realised return: about equal at 5%, worse at 10% and 20%. It picks a higher minimum on validation, buys fewer notes (idle money earns zero), and the notes it buys default more often, so the better ranking of the PD (AUC 0.677 against 0.636) does not turn into better choices under this rule. Juan chose to report it as measured and to review the rule in a later step (D-097).

---

## 6. F4 Automation

Every decision of F4 was explained to Juan and taken by him one at a time on 2026-11-24 (D-098 to D-108). Scope (D-098): step 4.1 plus a simulated clock; step 4.2 moves to F5 as the replayer that calls the API (D-008). Two pull requests: (1) the flow and Prefect in docker compose; (2) the clock, the retraining cadence and the alerts.

**The design in one page**

| Topic | Decision |
|---|---|
| Orchestrator | Prefect 3: server and worker in compose (D-099) |
| Installation | `train` dependency group; FastAPI, python-dateutil and python-slugify downgraded, no known vulnerability; server and worker from the `train` image (D-103) |
| Tasks | Cut where the result is stored; only identifiers travel; PD and LGD apart (D-100) |
| Publishing | Not a task of the system: the simulator runs before the flow (D-043, D-105) |
| Loading | Catches up every delivered month up to the one asked (D-104) |
| Idempotency | Key (model, training set version, commit) as tags of the registered versions; promotion in two phases (D-101) |
| Retries | Only transient failures: 3 attempts after 10, 30 and 90 s; anything else stops the flow (D-102) |
| Cadence | Every month is loaded; versioning and retraining in January, April, July and October; a parameter (D-106) |
| Clock | An `advance` flow of the simulated world: publishes the next month, runs the system's flow, then records the month in `sim.clock`; `replay` loops it; schedule paused by default (D-107) |
| Alerts | Table `ops.alerts`: failed flows, promotions, rejections, rollbacks; the channel comes with Grafana in F6 (D-108) |

### First pull request: the flow

```
 simulator (simulated world, D-043)         system (Prefect flow "monthly", D-100)
 make publish PERIOD=...                    load ---> version ---> train-pd ---> train-lgd
   writes data/landing/YYYY-MM/*.csv.gz       |          |             |              |
                                            Postgres   training      MLflow:         MLflow:
                                            raw, clean sets +        runs, registry, same for
                                            (D-104)    manifest      promotion       the LGD
```

`credit_risk.flows` holds only coordination: each task is one call to a function of `src/` (`ingest.catch_up`, `snapshot.build`, `pipeline.retrain_pd`, `pipeline.retrain_lgd`), and the tasks hand on a month, a training set version, a registered version and the covered terms. The flow's folders are a parameter (`Paths`, a pydantic model so the server can send it as JSON, E-038). `python -m credit_risk.flows run 2014-01` runs it in process; `serve` registers the deployment `monthly/monthly` and waits for runs (the `worker` service); `server` creates the database `prefect` and starts the Prefect server (the `prefect` service, web interface on `localhost:4200`). `make flow PERIOD=2014-01` published with the simulator and then sent a run through the server (replaced in the second pull request by `make advance` and `make replay`, D-107).

**Compose.** Two services from the `train` image (D-103): `prefect` (server, metadata in the database `prefect` of our Postgres) and `worker` (environment pointing at `postgres`, `mlflow` and `prefect` inside the compose network). The worker reads the deliveries from `./data/landing`, read only, and writes reports and training sets to a volume of its own. The `train` image carries the commit of its code (`CREDIT_RISK_COMMIT`, a build argument passed by `make build` and CI), needed by the key of D-101.

**Idempotency of training (D-101).** `pipeline.retrain_pd` and `retrain_lgd` first ask the registry for a challenger tagged with the same training set and commit. If there is one, nothing is trained: the version is reused and its promotion finished if needed. If not, any finished run of that key left by an earlier attempt is marked `FAILED` and `orphan`, and the model is trained. The baseline is registered before the challenger. `registry.promote` writes the verdict, evidence and what it was judged against first (`promotion.decision`), then moves the alias, then writes `promotion.outcome`; a second call returns the stored verdict.

**Retries (D-102).** `flows.is_transient` decides: `psycopg.OperationalError`, and MLflow requests that got no answer, timed out or got a 5xx answer. Every task has `retries=3`, `retry_delay_seconds=[10, 30, 90]` and `retry_condition_fn` built on it.

**Measured** (2026-11-24, cloud machine): on the made-up source of the tests (56 months, 3,300 matured loans, about 1,000 defaults), loading every month takes about 15 s, a second catch-up with nothing changed 0.2 s, PD and LGD with 3 search trials about 15 s; the whole flow about 30 s. The `train` image is 1,387 MB (budget 1,500 MB).

**Tests** (T16, approved by Juan on 2026-11-24): retry classification and counts (T16.1, T16.2); the idempotency key, the orphan runs and the idempotent promotion (T16.3 to T16.5); PD and LGD apart give the same models (T16.6); the whole cycle on small data (T16.7); a critical validation failure stops the flow (T16.8); running again duplicates nothing (T16.9); the Prefect server, its database and a run through the deployment (T16.10). B7 also checks that `serve` cannot import Prefect. Unit tests run MLflow on a local SQLite store (E-037).

| Error | What happened |
|---|---|
| E-037 | SQLAlchemy deprecation warning from MLflow's SQLite store, turned into an error; ignored for that message only |
| E-038 | A dataclass parameter could not be rebuilt from JSON by the server; now a pydantic model |
| E-039 | The first flow imported the simulator; T1.11 caught it; D-105 |
| E-040 | T16.8 expected raw unchanged; raw keeps deliveries by design (D-044) |
| E-041 | Prefect could not create its home folder in the image (users without home); `PREFECT_HOME=/tmp/prefect` |

### Second pull request: the simulated clock, cadence and alerts

```
 simulated world (credit_risk.simulator)          system
 flow "advance" (deployment advance/advance,      flow "monthly" (subflow)
 every 10 min, paused; or make advance)             load                       every month
   1. sim.clock -> next month (2014-01 if empty)    if Jan, Apr, Jul, Oct (D-106):
   2. publish its delivery (history on first run)     version -> train-pd -> train-lgd
   3. run "monthly" for it  ----------------------->  verdicts -> ops.alerts (promoted, rejected)
   4. only then write the month in sim.clock        on failure -> ops.alerts (flow_failed)
 flow "replay" (make replay TO=YYYY-MM): advance until TO
```

**Clock (D-107).** `credit_risk/simulator/clock.py` keeps "now", the last completed month, in the one row of `sim.clock`, a schema of the simulated world that the system never reads (T17.3). `advance` publishes the next month (`publish(..., since=month)` writes only its own files; the first run writes the whole history), runs `flows.monthly` as a subflow and writes the month only after it succeeds: a failure leaves the clock where it was and the next `advance` repeats the month. A new compose service, `clock`, serves the deployments `advance/advance` (interval of 10 minutes, paused: switch it on in the Prefect UI to watch the system live on its own) and `replay/replay`. It reads the source file read only from `./data/raw` and writes the deliveries to the volume it shares with the worker, so the worker no longer mounts `./data/landing`. `make advance` and `make replay TO=2014-12` send runs through the server and wait for them.

**Cadence (D-106).** `flows.retrains(period, cadence)`; `monthly` takes `cadence` (default `quarterly`), loads every month and returns after `load` in the months that do not retrain. Its summary carries `retrained` and the flow run id.

**Alerts (D-108).** `credit_risk/alerts.py` writes `ops.alerts` (migration `20261124150000`): kind, severity, month, flow, task, model, version, previous champion, message and details as JSON. The train tasks read the champion before and after training and record `rejected` (with the failed rules) and `promoted`; a unique index on kind, model and version keeps a verdict from being recorded twice when a month runs again. The `on_failure` hook of `monthly` records `flow_failed` with the month, the failed task and the error; it waits up to 15 s for the server to record the failed task (E-042). `python -m credit_risk.registry rollback pd` records `rolled_back`. Until F6, the alerts are read with SQL: `SELECT at, kind, severity, period, task, model, version, message FROM ops.alerts ORDER BY at DESC;`.

**Measured** (2026-11-24, cloud machine): the clock story of the integration tests (four advances on the made-up source, two of them retraining, one failing) takes about 60 s. The real year of T17.9 (empty clock, 2014-01 to 2014-12, real file, real number of trials) took 25 min (1,487 s; the first month publishes and loads the whole history since 2007-06): 12 months, 4 training sets, no failed flow. Verdicts:

| Retraining | PD challenger | LGD challenger |
|---|---|---|
| 2014-01 | v2 promoted (against the baseline, D-090) | v2 rejected: not better than the noise; the baseline stays champion (D-087) |
| 2014-04 | v3 rejected: not better than the noise, a key segment clearly worse | v3 rejected: not better than the noise |
| 2014-07 | v4 promoted | v4 rejected: not better than the noise |
| 2014-10 | v5 promoted | v5 rejected: not better than the noise |

At the end of 2014 the PD champion is v5 and the LGD champion is still the mean by grade (v1): as at T0 (D-087), no LGD model beats it. Every verdict has its alert in `ops.alerts`.

**Tests** (T17, approved by Juan on 2026-11-24): cadence (T17.1); the failure hook (T17.2); the system never touches `sim` (T17.3); advance from an empty clock (T17.4); a failed advance repeats its month (T17.5); only cadence months retrain (T17.6); every event in `ops.alerts` once (T17.7); the deployments and `replay` (T17.8); a real year, 2014 (T17.9).

| Error | What happened |
|---|---|
| E-042 | The failure hook asked for the task runs before the server had recorded the failed task; it now asks again for up to 15 s |

---

## 7. F5 Deployment

Every decision of F5 was explained to Juan and taken by him one at a time, on 2026-11-24 and 2026-11-25 (D-109 to D-136). Scope (D-109): step 5.1 (the API), the old step 4.2 as a replayer that sends each month to the API (D-098), and step 5.2 (a versioned image published by CD). Three pull requests: (1) the API and the predictions table; (2) the replayer in the simulated clock; (3) the published image.

**The design in one page**

| Topic | Decision |
|---|---|
| Models | The champions of the MLflow registry, by their alias `champion` (D-110) |
| New champions | The flow notifies `POST /admin/reload` after a promotion; the API also polls the aliases every 60 s; PD, LGD and buy rule are swapped as a whole, and a failed load keeps the set in use and alerts (D-111) |
| Answer | PD, LGD, expected loss in dollars (PD x LGD x EAD, EAD = amount funded) and as a rate, expected return, whether it passes the buy threshold, four main reasons, versions; the monthly cap stays with the investor (D-112) |
| Predictions table | `serving.predictions`: one row per prediction, columns for what is filtered, JSONB for the request, the features and the SHAP vector (D-113) |
| Duplicates | Unique (loan, PD version, LGD version); a repeat returns the stored answer (D-114) |
| Request log | One JSON line per request on stdout and one row in `serving.requests`; refused requests keep their body and errors (D-115) |
| Input | Listings as the provider delivers them (every column as text), cleaned with the code of the monthly load; 422 names the column (D-116) |
| Batch | Up to 1,000 loans, a result per loan; only a malformed batch is refused whole (D-117) |
| Access | API keys in `X-API-Key`, one list per permission (predict, admin), several valid at once; `/health` open (D-118) |
| Installation | FastAPI 0.150 and uvicorn in the main dependencies, one lock (D-119) |
| Buy threshold | The buy rule is registered in MLflow like a model, chosen again when the champion pair changes (D-120) |
| Writing | Each prediction is written before it is answered, in the request's transaction; database down gives 503 (D-121) |
| Load test | Open load of 20 requests a second, p95 under 200 ms; capacity measured apart (D-122) |
| Investor | The replayer is the simulated investor, a step of `advance` after publishing a month and before the system's flow (D-123); from the month after T0 (D-127) |
| Purchases | Reported to `POST /purchases` and stored in `serving.purchases` (D-124), each naming the `prediction_id` of its answer (D-126) and its amount in notes of 25 dollars (D-128), by the client's own order number (D-129) |
| Investor failures | The API not answering is retried 3 times, then the clock stops; a refused listing is not bought and is counted (D-125) |
| Registry | GitHub Container Registry, with the token of each CI run; ECR in F7 (D-130) |
| Published images | `credit-risk-serve` and `credit-risk-train`, from the same commit, public (D-131, D-136) |
| Tags | `sha-abc1234` (never rewritten) and `main` on every merge; `X.Y.Z` on a release tag `vX.Y.Z`, without building again (D-132) |
| Publication | A fifth CI job after the four pass on main, with the images they tested (D-133); Trivy blocks HIGH and CRITICAL first (D-135) |
| Smoke test | The published images answer a real prediction before `main` moves to them (D-134) |

### First pull request: the API and the predictions table

```
 monthly flow (Prefect)                                API (credit_risk.api, serve image)
 load -> version -> train-pd -> train-lgd              POST /predict, /predict/batch  (predict key)
                       |           |                     1. validate the listing (pydantic, strict)
                       v           v                     2. clean + features (same code as the load)
                    buy-rule (D-120): minimum on         3. PD, LGD, SHAP, EL, expected return,
                    validation for the champion pair        threshold of the buy rule
                       |                                 4. INSERT request + predictions, one
                       v                                    transaction, ON CONFLICT do nothing
                    reload: POST /admin/reload ------->  POST /admin/reload  (admin key)
                    (if a champion or the rule moved)      loads pd + lgd + buy_rule by alias,
                    failure -> ops.alerts reload_failed    swaps them in one assignment
                                                         poll every 60 s: same, if an alias moved
 MLflow registry: pd, lgd, buy_rule @champion  <-------  GET /health/live (process), /health (ready)
```

**The package.** `credit_risk.api` has five modules. `settings` reads the keys and options (`API_*`). `champions` keeps the set in use: `Holder.refresh()` loads PD, LGD and buy rule from the registry, checks their types, and replaces the set in one assignment under a lock, so a request reads one set from start to end (T18.9). `scoring` turns typed listings into answers with the functions of F3: `features.build_features`, `PDModel.predict_pd`, `LGDModel.predict_lgd`, `explain.explain` and `business.scheduled_interest`; the PD's model matrix is built once and shared with its explanation. `store` writes to Postgres through a pool of connections. `app` holds the endpoints, the key checks and the middleware that times each request, writes its log line and records refused requests. `python -m credit_risk.api` serves it with uvicorn, one process per container: a reload has to reach the process that serves, so the API grows by adding containers, never workers inside one.

**Input (D-116).** The body is a listing with the columns of the delivery contract (`contracts.LISTING_COLUMNS`), every value as text or null, exactly as the replayer reads the monthly file. A pydantic model built from the contract refuses unknown fields and requires `id` and every column the model reads (`features.INPUTS`), even when empty. Then `cleaning.convert` applies the rules of the monthly load and `build_features` builds the 30 features; a value the cleaning cannot convert is a 422 naming its column. A term the PD does not cover is answered with `covered: false` and no risk (D-070), and stored.

**The answer.**

```json
{
  "request_id": "...",
  "prediction": {
    "loan_id": 12345, "covered": true, "note": null,
    "pd": 0.143, "lgd": 0.83, "ead": 10000.0,
    "expected_loss": 1186.9, "el_rate": 0.1187, "expected_return": 0.071,
    "threshold": {"available": true, "minimum": 0.135, "passes": false},
    "reasons": [{"feature": "grade", "value": "D", "contribution": 0.41}, "..."],
    "versions": {"pd": "5", "lgd": "1", "buy_rule": "2", "api": "0.1.0"},
    "stored_earlier": false
  }
}
```

If the buy rule in use was chosen for another PD and LGD pair, or there is none yet, the risk is served and `threshold.available` is false (T18.10). The batch endpoint answers `{"results": [...]}` in the order sent, each item either `prediction` or `errors`.

**Tables** (migration `20261124180000`). `serving.requests`: one row per request (id, time, endpoint, client name, status, latency, number of loans, refused, versions; body and errors only when refused). `serving.predictions`: one row per loan and pair of models, linked to its request: versions, `covered`, PD, LGD, EAD, expected loss, rate and return, minimum and `passes`, base value, the SHAP vector of the 30 features, the four reasons, the features and the request as JSONB. Checks in the database: PD and LGD in [0, 1], and a covered row has PD, LGD and contributions. The unique constraint `predictions_once (loan_id, pd_version, lgd_version)` makes a repeat return the stored row, marked `stored_earlier` (T18.6). Request and predictions are written in one transaction before the answer leaves; if Postgres is down the answer is 503 and nothing is predicted (T18.7). Migration `20261124180100` adds the alert kinds `model_load_failed` (the API could not load a champion) and `reload_failed` (the flow could not notify the API).

**Buy rule (D-120).** `credit_risk.buy_rule`: after training, the task `buy-rule` reads the champion pair; if no buy rule is registered for it (tags `pd_version`, `lgd_version`), it chooses the minimum expected return on the validation split of the current training set with `business.choose_minimum` (D-084), at the cap K of D-085, with a bootstrap interval of the net return, logs a run with the required fields (D-079), registers it as the model `buy_rule` and moves its alias; if one exists (a rollback to an earlier pair), the alias goes back to it. Then the task `reload` notifies the API when a champion or the rule moved. A failed notice does not fail the flow: it records `reload_failed` and polling catches up within 60 s (T19.2).

**Keys (D-118).** `API_KEYS_PREDICT` and `API_KEYS_ADMIN` hold `name:key` pairs separated by commas; a key has at least 32 characters, compared in constant time; only the name reaches logs and tables. The flow sends `API_ADMIN_KEY`, the replayer `API_PREDICT_KEY`. Rotation by hand in compose, with no moment without a valid key: (1) add the new key to the list and restart the API (both valid); (2) give the client the new key; (3) remove the old one and restart. In AWS (F7) Secrets Manager does these steps on its own.

**Health.** `/health/live` answers while the process runs (the compose healthcheck). `/health` answers 200 only when the champions are loaded and Postgres answers, with the versions in use and the time of the last load; otherwise 503 (T18.8).

**Compose.** A new service `api` from the `serve` image, port `127.0.0.1:8000`, with Postgres and MLflow in its environment; the worker gets `API_URL=http://api:8000` and the admin key. The interactive documentation is at `http://localhost:8000/docs`.

**Measured** (2026-11-24, cloud machine, one API process). Scoring one loan with its explanation and storing it: about 12 ms of work (31 ms before the changes of E-044). Open load of 20 requests a second for 60 s (T18.13): p95 30 ms. Capacity with 20 clients always waiting: about 70 answers a second per process. A batch of 1,000 loans: about 1 s. For scale, Lending Club listed at most about 40,000 loans a month in 2018, under one a minute. The real delivery of 2014-02 (15,269 loans, models trained at T0) through the API in batches of 1,000 gives exactly what scoring the month in process gives (T18.15): 10,943 covered (36 months), minimum expected return +0.135, 2,915 pass the threshold.

**Tests** (T18 and T19, approved by Juan on 2026-11-24): the full answer (T18.1); uncovered terms (T18.2); invalid input (T18.3); batches (T18.4); keys (T18.5); duplicates (T18.6); synchronous writing (T18.7); start and readiness (T18.8); reload (T18.9); threshold of another pair (T18.10); what is stored (T18.11); logs (T18.12); load (T18.13, changed by D-122); compose and the `serve` image (T18.14); a real month (T18.15); the buy rule in the flow (T19.1) and the notice to the API (T19.2). T16.8 and T17.6 now expect the tasks `buy-rule` and `reload`.

| Error | What happened |
|---|---|
| E-043 | Starlette's test client asks for `httpx2`; httpx kept and the warning ignored by its message |
| E-044 | The load test missed its objective: 31 ms of work per loan; polars called once per column, the PD's matrix built three times |
| E-045 | The first load test ran its clients in the server's process (the GIL) |
| E-046 | The real-month test dropped empty columns; the API rightly refused the loans |

### Second pull request: the simulated investor and its purchases

```
 simulated world: flow "advance" for month M                    system
   1. publish M (and the history on the first run)
   2. investor (replayer, D-123), if M is after T0 (D-127)
        listings of M, 1,000 at a time -------------------------> POST /predict/batch
                                         <-- prediction_id, risk, passes threshold
        K = 10% of the listings of M-1 (D-085)
        those that pass, in listing order, up to K, 25 dollars each
        order "M-loan", prediction_id, 25 ---------------------> POST /purchases
                                                                   -> serving.purchases
        record M in sim.invested
   3. the system's flow "monthly" for M (load; retraining in the cadence months)
   4. write M in sim.clock
```

**The investor** (`credit_risk.simulator.replayer`). It belongs to the simulated world, as the clock: in production the investor is a client of the API. Each month after T0 it reads the month's listings as the provider delivered them and sends them to `/predict/batch` in batches of 1,000; keeps the answers that pass the buy threshold; applies its cap with `business.buy` (the same function as the business metric of F3: K is 10% of the loans listed the month before, in listing order, D-085); and reports the purchases to `/purchases`. Its key is a predict key (`API_PREDICT_KEY`, client name `replayer`). It runs before the system's flow, so in a retraining month its loans are decided by the champions of the month before (T21.3). The month is recorded in `sim.invested` (migration `20261125090100`) with its counts; a month the clock repeats because the system's flow failed is not sent again, since the investor already acted on it.

**Failures (D-125).** No connection, a timeout or a 5xx answer of the API raises `ApiUnavailableError`, retried by Prefect three times after 10, 30 and 90 s; then `advance` fails and the clock stays. A listing refused with 422 is counted (`refused`) and not bought. A refused purchase stops the month (`InvestorError`): it would be a bug. Repeating a month buys nothing twice: predictions are stored once per loan and pair (D-114) and purchases once per order number (D-129).

**Purchases (D-124, D-126, D-128, D-129).** Every answer now carries `prediction_id`. `POST /purchases` takes up to 1,000 purchases:

```json
{"purchases": [{"order_id": "2014-02-12345", "prediction_id": 8812, "amount": 25}]}
```

and answers 200 with one result per purchase, in order: `created` or `stored_earlier` with the stored purchase, or `refused` with 409 (the order number was used for another purchase) or 422 (unknown prediction, an amount that is not a positive multiple of 25, a client's share above the loan's amount, or a malformed purchase). A malformed request (empty, more than 1,000, a wrong key) is a 422 for the whole request. Each purchase is marked against the rule of its answer: `passes`, `below_minimum`, `no_threshold` or `not_covered`; exceptions are recorded, never refused. `credit_risk.api.purchases.judge` decides; the store reads what it needs and writes what it decides in the request's transaction, under a lock on the client's order and one on its share of the loan (`pg_advisory_xact_lock`), so two requests at once cannot both create an order or overfill a loan (T20.5).

**Table** (migration `20261125090000`). `serving.purchases`: one row per order, linked to its request and its prediction: client, order number, loan, amount (numeric, checked to be a positive multiple of 25), policy, time. Unique (client, order number).

**Compose.** The `clock` service gets `API_URL=http://api:8000` and `API_PREDICT_KEY`, and starts after the API is healthy.

**Measured** (2026-11-25, cloud machine). On the made-up source of the tests (about 15 listings a month), the clock story with the investor takes about 80 s, as before. The real year of T17.9 with the investor took 32 min (1,906 s, with the unit tests running at the same time; 25 min without the investor in F4), with the same verdicts as in F4 (PD champion v5, LGD still the mean by grade). Every listing from 2014-02 went through the API, with no refusal:

| Month | Listings | Pass the threshold | K | Bought |
|---|---|---|---|---|
| 2014-02 | 15,269 | 2,899 | 1,562 | 1,562 |
| 2014-03 | 16,513 | 3,344 | 1,526 | 1,526 |
| 2014-04 | 19,071 | 3,841 | 1,651 | 1,651 |
| 2014-05 | 19,099 | 2,897 | 1,907 | 1,907 |
| 2014-06 | 17,179 | 2,108 | 1,909 | 1,909 |
| 2014-07 | 29,306 | 3,844 | 1,717 | 1,717 |
| 2014-08 | 18,814 | 4,934 | 2,930 | 2,930 |
| 2014-09 | 10,606 | 2,789 | 1,881 | 1,881 |
| 2014-10 | 38,783 | 10,186 | 1,060 | 1,060 |
| 2014-11 | 25,054 | 5,036 | 3,878 | 3,878 |
| 2014-12 | 10,307 | 1,964 | 2,505 | 1,964 |

December is the case Juan asked about: fewer loans pass than K, so all of them are bought and the rest of the budget stays idle (D-085). The months after a large one (2014-08 after 2014-07, 2014-11 after 2014-10) have a large K; the cap follows last month's listings, as D-085 decided.

**Tests** (T20, T21, approved by Juan on 2026-11-25): a purchase recorded (T20.1); order numbers (T20.2); refusals (T20.3); exceptions recorded (T20.4); the database's constraint, locks and transactions (T20.5); the investor's rule by hand (T21.1); months after T0, every listing once (T21.2); the champions of the month before (T21.3); failures (T21.4); purchases equal to the rule on the predictions (T21.5). T17.9 also checks the investor on the real year. T17.4 to T17.8 run with the API in a process of its own.

| Error | What happened |
|---|---|
| E-047 | The clock story expected several batches a month with batches of 40; a made-up month has 15 listings |

### Third pull request: versioned images in a registry

Continuous integration checks every change; continuous delivery keeps every version that passed as a product ready to run. Each merge to main ends with two images in GitHub Container Registry, named by their commit, that anyone can download and start. Deploying them somewhere (continuous deployment) comes with AWS in F7.

```
 merge to main --> CI on main: quality, tests, secrets, integration
                     | integration keeps the serve and train images it tested (D-133)
                     v only if the four pass
                   publish (the only job that may write packages):
                     1. load those images; build nothing
                     2. Trivy: a HIGH or CRITICAL not in .trivyignore.yaml -> stop (D-135)
                     3. push ghcr.io/juangarridogarcia/credit-risk-{serve,train}:sha-abc1234
                        (a commit tag that holds another image -> stop; never rewritten)
                     4. pull them back by digest; they must be the tested images
                     5. smoke test (tests/smoke.py) on what was pulled -> stop if it fails
                     6. tag main on the same digests, in the registry (D-134)

 git tag v0.2.0 --> CI on the tag, then publish:
                     pull sha-<commit> (it must exist: merged to main first), Trivy,
                     smoke test, tag 0.2.0 on the same digests; nothing pushed (D-132)
```

A tag is a name on an image, as a branch is a name on a commit. Moving `main` changes no image: it moves the name to the newest one that passed everything, so `docker pull ghcr.io/juangarridogarcia/credit-risk-serve:main` always gives the last good version and `:sha-abc1234` gives exactly that commit, for ever.

**Built once.** The job `integration` already builds and tests both images. On main it saves them (`docker save`, an artefact of the run kept one day) with their image ids in `tested.json`; `publish` loads them and checks each id before pushing and again after pulling back. Pulling back by digest checks the registry itself: the upload, the permissions, the package.

**The program** (`ci/`, outside the package: no image carries it). `ci/tags.py` turns the ref and commit of the run into a plan: repositories (owner lowercased, since GHCR refuses capitals), commit tag, tag to move, and whether to push. `ci/publish.py` carries it out through `docker` and `docker buildx imagetools`; the final tag is put in the registry on the very manifest that was smoke tested, without pulling or pushing again. A failure at any step leaves `main` and every version where they were; an image that failed its smoke test stays in the registry under its commit, to be looked at.

**The smoke test** (`tests/smoke.py`). Under a compose project of its own and on free ports, it starts Postgres, the MLflow server (from train) and the API (from serve) with the images given, never building or pulling; applies the migrations; registers made-up champions as the API tests do; and requires the commit and version inside train, `/health` 200 and one `/predict` with PD, LGD and expected loss in range. Everything it started is removed at the end. It found a real bug on its first run (E-048).

**Runs on main wait their turn.** Runs of pull requests are still cancelled by a newer push; runs of main and of tags are not, because a cancelled publication could leave `main` moved on serve and not on train.

**The Monday scan** (`security.yml`) now pulls the published `main` images and scans them with Trivy, instead of rebuilding them: a vulnerability found after publishing shows up there.

**Visibility (D-136).** GHCR creates a package private. After the first publication Juan makes each package public once (package settings, "Change visibility"); it cannot be made private again.

**Tests** (T22, approved by Juan on 2026-11-25): names and tags (T22.1); the rules of the workflows (T22.2); the smoke test on the images of the pull request, passing and failing (T22.3); the whole publication rehearsed against a throwaway registry in a container (T22.4).

| Error | What happened |
|---|---|
| E-048 | The API in compose could not load its champions: the MLflow server refused its Host name |
