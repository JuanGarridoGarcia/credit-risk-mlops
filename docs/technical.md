# Technical document

The full detail of the project, one section per step of the playbook: what was built, how, which numbers came out, which decisions and errors happened, and how it was checked. The README is the short version; this is the manual. Format decided in D-035.

Related documents: [problem definition](problem.md), [data audit](data_audit.md), [decision log](decisions.md), [error log](errors.md).

## Contents

1. Tracking sheet
2. F0 Framing (steps 0.1, 0.2)
3. F1 Foundations (steps 1.1 to 1.4)

---

## 1. Tracking sheet

Status of every step of the playbook. Updated in every pull request.

| Phase | Step | Status | PR | Notes |
|---|---|---|---|---|
| F0 Framing | 0.1 Problem, metric, baseline and constraints | Done | #1 | D-001 to D-011 |
| | 0.2 Data audit | Done | #1 | D-012 to D-018; 9.4 to 9.6 deferred to the simulation design |
| F1 Foundations | 1.1 Repository, environment and code quality | Done | #2 | D-019 to D-024, D-037 |
| | 1.2 Docker and docker compose | Done | #2 | D-025 to D-027 |
| | 1.3 Minimal CI | In review | #2 | D-028 to D-032, D-038. Lint-failure check done; branch protection set by Juan on 2026-11-22 |
| | 1.4 Documentation skeleton | In review | #2 | D-033 to D-036 |
| F2 Data | 2.1 Idempotent ingestion | Pending | | |
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
| B5 | `tests/integration/test_image.py` | The image runs as non-root; no `.env*` file anywhere in it; no password, secret, token, Kaggle or AWS variable in its configuration or build history; the default command prints the right version; size at most 300 MB (measured 211 MB) |

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
