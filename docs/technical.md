# Technical document

The full detail of the project, one section per step of the playbook: what was built, how, which numbers came out, which decisions and errors happened, and how it was checked. The README is the short version; this is the manual. Format decided in D-035.

Related documents: [problem definition](problem.md), [data audit](data_audit.md), [decision log](decisions.md), [error log](errors.md), [validation rules](validation_rules.md).

## Contents

1. Tracking sheet
2. F0 Framing (steps 0.1, 0.2)
3. F1 Foundations (steps 1.1 to 1.4)
4. F2 Data (steps 2.1 to 2.4)

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
| F2 Data | 2.1 Idempotent ingestion | In review | | D-039 to D-052; E-013 to E-019 |
| | 2.2 Data validation | Pending | | |
| | 2.3 Data versioning | Pending | | |
| | 2.4 Features | Pending | | |
| F3 Model | 3.1 Baseline | Pending | | |
| | 3.2 Tracking and experiments | Pending | | |
| | 3.3 Model tests and promotion rules | Pending | | |
| | 3.4 Model registry | Pending | | |
| | 3.5 Explainability and model card | Pending | | |
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
  uv        astral/uv:0.11.32 (by digest)      only to copy the uv binary
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
| T3 Loading (13) | `tests/integration/test_ingest.py`, `tests/data/test_ingest_data.py` | 1 migrations up, down, up on an empty database; 2 rows and log of a load; 3 same file twice changes nothing; 4 corrected delivery replaces the month with no ghost row; 5 a failure (truncated record at the end; a primary key violation during `COPY`) leaves the month as it was and is logged; 6 deleting a month leaves the others; 7 text survives Postgres; 8 SQL injection stored as text; 9 clean equals the cleaned delivery, with Postgres types; 10 clean rebuilt from raw without the delivery file; 11 missing delivery names the file; 12 a loan in two months rejected; 13 real data: all 142 months load with the audit counts |

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
