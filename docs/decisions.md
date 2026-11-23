# Decision log

Every design decision of the project: when, what, which alternatives were considered, why, and what it implies. All decisions are taken by Juan; Claude proposes and debates. Format decided in D-033.

Rules: a decision is never deleted or rewritten. If it changes, a new decision supersedes it and the old one is marked `Superseded by D-0XX`. Statuses: `Active`, `Proposed` (waiting for Juan), `Superseded`.

## Index

| ID | Date | Step | Decision | Status |
|---|---|---|---|---|
| [D-001](#d-001) | 2026-11-20 | 0.1 | The user is an investor deciding at listing time | Active |
| [D-002](#d-002) | 2026-11-20 | 0.1 | Production serves PD, LGD and expected loss | Active |
| [D-003](#d-003) | 2026-11-20 | 0.1 | Lifetime default target; 12-month default rate as early warning | Active |
| [D-004](#d-004) | 2026-11-20 | 0.1 | PD baseline: logistic regression on `grade` | Active |
| [D-005](#d-005) | 2026-11-20 | 0.1 | LGD baseline: mean LGD by grade | Active |
| [D-006](#d-006) | 2026-11-20 | 0.1 | Model metrics: ranking and calibration | Active |
| [D-007](#d-007) | 2026-11-20 | 0.1 | Business metric: realised return at equal budget | Active |
| [D-008](#d-008) | 2026-11-20 | 0.1 | Single prediction path: the API | Active |
| [D-009](#d-009) | 2026-11-20 | 0.1 | Constraints: explainability, latency, cost, fairness, no future data | Active |
| [D-010](#d-010) | 2026-11-20 | 0.1 | Buy rule decided in F3 | Active |
| [D-011](#d-011) | 2026-11-20 | 1.4 (advanced) | Decision log created in F0 | Active |
| [D-012](#d-012) | 2026-11-21 | 0.2 | Data source: full Lending Club file pinned by SHA-256 | Active |
| [D-013](#d-013) | 2026-11-21 | 0.2 | PD label mapping; old-policy loans removed | Active |
| [D-014](#d-014) | 2026-11-21 | 0.2 | Only fields proven visible at listing can be features | Active |
| [D-015](#d-015) | 2026-11-21 | 0.2 | Free text not used in v1 | Active |
| [D-016](#d-016) | 2026-11-21 | 0.2 | Late-starting fields enter at a retraining | Active |
| [D-017](#d-017) | 2026-11-21 | 0.2 | LGD trained on charge-offs at least 12 months old | Active |
| [D-018](#d-018) | 2026-11-21 | 0.2 | `addr_state` and zip code are not features | Active |
| [D-019](#d-019) | 2026-11-22 | 1.1 | Dependency manager: uv | Active |
| [D-020](#d-020) | 2026-11-22 | 1.1 | Python 3.12 | Active |
| [D-021](#d-021) | 2026-11-22 | 1.1 | `src/` layout, package `credit_risk`, notebooks never hold production code | Active |
| [D-022](#d-022) | 2026-11-22 | 1.1 | Code quality: ruff + mypy | Active |
| [D-023](#d-023) | 2026-11-22 | 1.1 | pre-commit hooks | Active |
| [D-024](#d-024) | 2026-11-22 | 1.1 | Audit notebook dependencies move into a uv group with the exact F0 versions | Active |
| [D-025](#d-025) | 2026-11-22 | 1.2 | Docker base image: `python:3.12-slim`, two stages, pinned by digest, non-root | Active |
| [D-026](#d-026) | 2026-11-22 | 1.2 | Minimal image now, plus a test stage | Active |
| [D-027](#d-027) | 2026-11-22 | 1.2 | docker compose holds only Postgres 18 for now | Active |
| [D-028](#d-028) | 2026-11-22 | 1.3 | CI: four parallel jobs on every PR and push to main | Active |
| [D-029](#d-029) | 2026-11-22 | 1.3 | Scheduled security scans and Dependabot | Active |
| [D-030](#d-030) | 2026-11-22 | 1.3 | Actions pinned by commit hash; workflows read-only | Active |
| [D-031](#d-031) | 2026-11-22 | 1.3 | Coverage measured with branches; minimum set in F2 | Active |
| [D-032](#d-032) | 2026-11-22 | 1.3 | Branch protection of `main`, no bypass, no required approval | Active |
| [D-033](#d-033) | 2026-11-22 | 1.4 | Decision log format: index plus one card per decision | Active |
| [D-034](#d-034) | 2026-11-22 | 1.4 | Error log format; F0 errors moved into it | Active |
| [D-035](#d-035) | 2026-11-22 | 1.4 | README as showcase, `docs/technical.md` as manual | Active |
| [D-036](#d-036) | 2026-11-22 | 1.4 | Repository documents in English | Active |
| [D-037](#d-037) | 2026-11-22 | 1.1 | Work branch named by the system | Active |
| [D-038](#d-038) | 2026-11-22 | 1.3 | Base image patch not yet published upstream: wait for the official image | Active |
| [D-039](#d-039) | 2026-11-23 | 2.1 | Simulated arrival: listings and outcomes as two separate streams | Active |

## Decisions

D-001 to D-018 were recorded in F0 as a table. Their text is unchanged; they predate the card format, so they have no separate Context and Consequences fields.

<a id="d-001"></a>
### D-001 The user is an investor deciding at listing time

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: The user is an **investor who decides whether to buy each loan when it is listed**
- **Alternatives considered**: Lender deciding whether to approve the application; portfolio valuation (expected loss of the book)
- **Why**: `grade` and the interest rate are set by Lending Club and are visible to an investor at listing, so the features fit this decision. As a lender we would be using the lender's own score to decide, and rejected applications are not in the data

<a id="d-002"></a>
### D-002 Production serves PD, LGD and expected loss

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: Production includes **PD, LGD and Expected Loss**; the API returns all three
- **Alternatives considered**: PD only, LGD and EL later as a batch extension
- **Why**: The investor needs to know how much would be lost, not only whether the loan defaults: a high-PD loan at a high rate can still be worth buying. PD only was proposed to limit scope and withdrawn

<a id="d-003"></a>
### D-003 Lifetime default target; 12-month default rate as early warning

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: PD target = **default at any point in the loan's life**; the **default rate within 12 months** is used as an early-warning metric in monitoring
- **Alternatives considered**: 12-month default (Basel horizon) as the target
- **Why**: The Basel 12-month horizon serves a bank's annual capital. A buy-and-hold investor loses whatever defaults over the whole life (IFRS 9 uses lifetime loss once risk has increased). Lifetime labels arrive 3 to 5 years late, so a 12-month signal is needed to monitor in time. Juan first chose the 12-month target; Claude corrected its own recommendation after Juan chose D-001. The early-warning metric depends on the data having a default date (checked in step 0.2)

<a id="d-004"></a>
### D-004 PD baseline: logistic regression on `grade`

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: PD baseline = **logistic regression on `grade` only**
- **Alternatives considered**: Constant default rate; the research-phase model
- **Why**: Answers whether the model knows more than the grade the investor already sees for free. Known risk: the gain may be small because `grade` dominates the PD

<a id="d-005"></a>
### D-005 LGD baseline: mean LGD by grade

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: LGD baseline = **mean LGD of the defaulted training loans of each grade**; the global mean is reported as a reference
- **Alternatives considered**: Global mean LGD (constant)
- **Why**: Same question as D-004, so the whole baseline EL is "what an investor can compute from the grade alone". The constant is kept as a reference to show how much the grade adds on its own

<a id="d-006"></a>
### D-006 Model metrics: ranking and calibration

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: Model metrics: PD by **AUC (and Gini), PR-AUC, Brier score and calibration by segment**; LGD by **RMSE, MAE and mean predicted vs observed by segment**; EL by **EL / realised loss**
- **Alternatives considered**: AUC only for the PD; recall as the PD metric
- **Why**: EL multiplies the PD, so the PD must be a real probability, not only a good ranking. Juan wants to study calibration further when it is built. Gini and PR-AUC are added: Gini is how credit teams report AUC, and PR-AUC measures performance on the minority class. Recall was discussed (Juan's concern: defaulters slipping through) and rejected as the model metric: it needs a threshold, and the model outputs a probability; recall alone is maximised by buying nothing; the asymmetric cost of the two errors is measured in money by the business metric (D-007). Recall, precision and the confusion matrix are reported in F3 at the buy-rule threshold

<a id="d-007"></a>
### D-007 Business metric: realised return at equal budget

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: Business metric: with the **same budget**, realised default rate, realised loss and **realised net return** of the portfolio bought by the model vs the one bought by the baseline
- **Alternatives considered**: Default rate and loss only
- **Why**: Net return is what an investor ultimately cares about. Step 0.2 confirms the data supports it

<a id="d-008"></a>
### D-008 Single prediction path: the API

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: **Single prediction path: the API** (single loan and batch endpoint), with every prediction stored. In the simulation, a replayer sends each month's loans to the API. A monthly job only monitors and decides retraining. The held portfolio is re-scored only when the champion model changes
- **Alternatives considered**: API for single loans plus a monthly batch that scores every loan of the month
- **Why**: Juan noticed that scoring the same loans twice is redundant. The investor decides at listing time, so one path is realistic, removes the risk of two implementations disagreeing and load-tests the API. Cost: a batch endpoint so the replay does not take hours

<a id="d-009"></a>
### D-009 Constraints: explainability, latency, cost, fairness, no future data

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: Constraints: explanation of every prediction (SHAP), API p95 below 200 ms, close to zero cost until AWS, review of `addr_state` and zip code as possible proxies for protected attributes, no information from the future
- **Alternatives considered**: None recorded
- **Why**: Credit scoring is high-risk under the EU AI Act; a slow score is useless at listing; personal project; indirect discrimination is illegal in credit

<a id="d-010"></a>
### D-010 Buy rule decided in F3

Date: 2026-11-20 · Step: 0.1 · Status: Active

- **Decision**: The exact **buy rule** is decided in F3
- **Alternatives considered**: Fix it now
- **Why**: It needs trained models and the noise of their metrics to set a threshold that makes sense. What is fixed now is how the rule is judged (D-007)

<a id="d-011"></a>
### D-011 Decision log created in F0

Date: 2026-11-20 · Step: 1.4 (advanced) · Status: Active

- **Decision**: This decision log is created in the F0 pull request, ahead of step 1.4
- **Alternatives considered**: Create it in F1 as the playbook orders
- **Why**: So that the decisions of F0 are recorded from day one. Step 1.4 does not depend on anything pending, which is the playbook's condition for advancing a step

<a id="d-012"></a>
### D-012 Data source: full Lending Club file pinned by SHA-256

Date: 2026-11-21 · Step: 0.2 · Status: Active

- **Decision**: Data source: Kaggle `wordsforthewise/lending-club`, file `accepted_2007_to_2018Q4.csv.gz` (2,260,668 loans, 2007 to 2018), pinned by SHA-256; column meanings from Lending Club's official dictionary (Kaggle `jonchan2003/lending-club-data-dictionary`)
- **Alternatives considered**: The cleaned research-phase dataset (`lending-club-loan-data-cleared`)
- **Why**: The cleaned dataset has no last payment date, so neither the label delay nor the 12-month early-warning metric (D-003) could be built. The full file has every column, including the payment fields needed for LGD and net return (D-007). Audit: `docs/data_audit.md`

<a id="d-013"></a>
### D-013 PD label mapping; old-policy loans removed

Date: 2026-11-21 · Step: 0.2 · Status: Active

- **Decision**: PD label: Fully Paid = 0; Charged Off and Default (121+ days late, 40 loans) = 1; Current, In Grace Period and Late = no label (still running). The 2,749 "does not meet the credit policy" loans (2007 to 2010) are **removed**
- **Alternatives considered**: Keep them with a flag (Claude's recommendation)
- **Why**: Juan: they were approved under an older, looser policy, so they would muddy the data, and a user of the API expects scores under the current policy. Cost: if the first training is in 2014-01, it loses 2,230 of its 14,308 matured loans (bad rate 27% vs 14% for the rest), which is taken into account in decision 9.5

<a id="d-014"></a>
### D-014 Only fields proven visible at listing can be features

Date: 2026-11-21 · Step: 0.2 · Status: Active

- **Decision**: A column can be a feature only if it is **proven** visible to the investor at listing, i.e. it appears in Lending Club's Browse Notes dictionary (`reports/data_audit/browse_notes_fields.md`). Dropped: the 32 post-issue columns, `funded_amnt_inv`, identifiers, `policy_code` and `mths_since_recent_bc_dlq` (likely available, not provable). `issue_d` only orders and splits in time; payments and recoveries only build targets
- **Alternatives considered**: Keep `mths_since_recent_bc_dlq` as probably available
- **Why**: Juan: if it cannot be proven it stays out completely. A leak makes validation look good and production fail. Free text (`emp_title`) is discussed separately

<a id="d-015"></a>
### D-015 Free text not used in v1

Date: 2026-11-21 · Step: 0.2 · Status: Active

- **Decision**: Free text columns (`emp_title`, `desc`, `title`) are **not used in v1**. A grouped `emp_title` (occupation or sector) may be tested later as a challenger in F3: it enters only if it beats the champion by more than the metric noise and passes a bias review
- **Alternatives considered**: Group `emp_title` and use it in v1
- **Why**: Income is already covered by `annual_inc`, `verification_status`, `dti`, `installment` and the joint fields. `emp_title` has 411,811 distinct values after lowercasing; the top 1,000 cover only 48% of loans, so grouping is a sub-project with its own error. Job title is a strong proxy for sex. `desc` stops in 2014

<a id="d-016"></a>
### D-016 Late-starting fields enter at a retraining

Date: 2026-11-21 · Step: 0.2 · Status: Active

- **Decision**: A model uses only columns filled throughout its training window. A column reported only from a given date (bureau fields 2012 and late 2015, second applicant 2017) enters at a retraining, logged as a "new data field" event. When exactly it enters is decided when the retraining policy is designed (proposal to discuss: a challenger trained on the shorter window that includes the new field, promoted only if it beats the champion by more than the metric noise)
- **Alternatives considered**: Use the columns from day one, with missing as a value
- **Why**: Missingness before the start date encodes the vintage, not the borrower (2007 to 2008 loans defaulted 21% to 26% and all lack `tot_cur_bal`). In production the field is never missing, so the learned rule would be useless. Fields legitimately empty (second applicant on individual loans) are handled with a joint-application flag

<a id="d-017"></a>
### D-017 LGD trained on charge-offs at least 12 months old

Date: 2026-11-21 · Step: 0.2 · Status: Active

- **Decision**: LGD is trained only on loans charged off **at least 12 months before** the training date
- **Alternatives considered**: Use every charged-off loan; wait 24 or 36 months
- **Why**: Recoveries arrive over time and the data has only the 2019 total, with no dates. Net recovery (share of funded amount): 2.7% at 0 to 5 months after charge-off, 6.0% at 6 to 11, 7.1% at 12 to 23, about 8.5% at 36 to 59. At 12 months most of it has arrived; waiting longer delays LGD labels by years for 1 to 2 points. Older charge-offs are also from another collection era, which a single snapshot cannot separate. Known limitation: amounts are as of 2019, a small unavoidable look-ahead in the simulation

<a id="d-018"></a>
### D-018 `addr_state` and zip code are not features

Date: 2026-11-21 · Step: 0.2 · Status: Active

- **Decision**: `addr_state` and `zip_code` are **not model features**. `addr_state` is kept only to monitor fairness: at each evaluation, performance and buy rates are compared across states to detect another feature acting as a proxy
- **Alternatives considered**: Keep the state and drop the zip code; keep both
- **Why**: Both are proxies for race (redlining), illegal in credit even if race is never seen; credit scoring is high-risk under the EU AI Act. Gain over `sub_grade` on an out-of-time test (train 2012 to 2014, test 2015): state +0.0021 AUC (95% CI +0.0016 to +0.0028), below the research-phase noise of 0.003; zip prefix -0.0003

<a id="d-019"></a>
### D-019 Dependency manager: uv

Date: 2026-11-22 · Step: 1.1 · Status: Active

- **Context**: The project needs every library pinned to an exact version and hash, so that any machine (cloud thread, CI, Docker, Juan's PC) installs the same environment.
- **Decision**: **uv**: dependencies declared in `pyproject.toml`, resolved into `uv.lock` (exact versions and hashes for Linux, Windows and macOS). One command, `uv sync`, prepares a clean clone.
- **Alternatives considered**: pip + `requirements.txt`; pip-tools; poetry; conda
- **Why**: One tool that also installs the right Python version, creates the environment and writes the lock. 10 to 100 times faster than pip or poetry, which matters because every thread, CI run and Docker build starts from scratch. Its lock file is universal across operating systems.
- **Consequences**: `uv.lock` is committed and CI checks it is in sync with `pyproject.toml` (`uv lock --check`). Every command runs with `--frozen`, so nothing is re-resolved silently.

<a id="d-020"></a>
### D-020 Python 3.12

Date: 2026-11-22 · Step: 1.1 · Status: Active

- **Context**: Libraries with compiled parts (numba under SHAP, MLflow, Evidently, the orchestrator) can lag months behind a new Python release. The F0 audit ran on 3.12.
- **Decision**: **Python 3.12**, fixed in three places that must agree: `.python-version`, `requires-python = ">=3.12,<3.13"` and the Docker base image `python:3.12-slim`.
- **Alternatives considered**: 3.13 (supported until 2029, slightly faster); 3.14 (most recent, real risk of lagging libraries)
- **Why**: The project lasts months, and 3.12 is supported until October 2028. The costliest risk is an incompatibility in the middle of F3 or F6. It keeps continuity with the audit.
- **Consequences**: Upgrading later is one PR that changes the three places; the CI, and from F3 the model tests, show whether anything broke.

<a id="d-021"></a>
### D-021 `src/` layout, package `credit_risk`, notebooks never hold production code

Date: 2026-11-22 · Step: 1.1 · Status: Active

- **Context**: The structure is the map of the project. With a flat layout, tests import the package folder directly from the repository, so they can pass while the installed package (the one that goes into Docker) is broken.
- **Decision**: `src/credit_risk/` as an installable package; `tests/unit/` and `tests/integration/`; `config/`, `docs/`, `notebooks/`, `reports/`, `data/` (git-ignored). Sub-packages (`data/`, `features/`, `models/`, `api/`, `monitoring/`) are created when a phase uses them, never empty. Notebooks import from `credit_risk`, never the other way round; useful notebook code moves to `src/` with tests.
- **Alternatives considered**: Flat layout (`credit_risk/` at the root)
- **Why**: With `src/`, Python finds the package only if it is installed, so packaging errors (for example a data file not shipped) fail in tests, not in production. Notebooks are not tested, have hidden state, cannot be imported and duplicate logic (training-serving skew, same argument as D-008).
- **Consequences**: Development uses an editable install (a link to `src/`). To prove the real, non-editable package is complete, the Docker image has a `test` stage that runs the unit tests against the installed package with `src/` deleted (D-026). Juan asked to also run notebooks top to bottom in CI: decided in F2, when data download exists.

<a id="d-022"></a>
### D-022 Code quality: ruff + mypy

Date: 2026-11-22 · Step: 1.1 · Status: Active

- **Context**: Some errors can be found without running the code. ruff reads each file on its own (patterns); a type checker follows values across the whole project.
- **Decision**: **ruff** for lint and formatting; **mypy** in strict mode on `src/`, more permissive on `tests/` (annotations not required) and not run on notebooks.
- **Alternatives considered**: black + flake8 + isort; ruff only; ruff + pyright; ty (new, too young to guard the CI)
- **Why**: ruff replaces three slower tools and is the current standard. mypy is the reference type checker in data projects and has a pydantic plugin (used by the settings and the API). A function that can return `None` reaching `expected_loss` is caught before running.
- **Consequences**: Every function in `src/` is annotated. Libraries with incomplete types get one-off exceptions, each with its reason. Types prove shape, not values: tests and runtime validation (F2, F5) still needed.

<a id="d-023"></a>
### D-023 pre-commit hooks

Date: 2026-11-22 · Step: 1.1 · Status: Active

- **Context**: Checks that depend on remembering to run them are skipped sooner or later; a secret pushed to GitHub stays in the history even if deleted.
- **Decision**: pre-commit runs on every commit: ruff check, ruff format, mypy, **gitleaks** (secrets), check-yaml, check-toml, files over 1 MB, end-of-file and trailing whitespace, no commit to `main`, and **nbstripout** except on notebooks that report results (explicit list: today only `00_data_audit.ipynb`). ruff and mypy run from the project environment, so their versions come from `uv.lock`. External hooks are pinned by commit hash (`pre-commit autoupdate --freeze`), the same rule as D-030.
- **Alternatives considered**: detect-secrets instead of gitleaks (needs a baseline file to maintain); no nbstripout; nbstripout on every notebook
- **Why**: Catch problems before the commit exists. Report notebooks keep their tables and charts visible on GitHub; work notebooks are stripped so PRs show only code.
- **Consequences**: pre-commit is the first barrier, not the only one: a hook can be skipped (`--no-verify`). CI runs the same checks and cannot be skipped (D-028). Dependabot does not update pre-commit hooks: they are refreshed with `pre-commit autoupdate --freeze` in a PR.

<a id="d-024"></a>
### D-024 Audit notebook dependencies move into a uv group with the exact F0 versions

Date: 2026-11-22 · Step: 1.1 · Status: Active

- **Context**: F0 pinned the audit environment in `notebooks/requirements-audit.txt` before the dependency manager was chosen.
- **Decision**: Group `notebooks` in `pyproject.toml` with the **exact** F0 versions; the txt file is deleted. Groups: main dependencies (go into the image), `dev` (tools), `notebooks` (exploration). The image installs only the main ones.
- **Alternatives considered**: Keep the txt as a separate frozen environment; group with version ranges
- **Why**: One versioning system. uv resolves all groups together, so a future conflict forces an upgrade: the audit is then re-run and its numbers compared, which turns every upgrade into a reproducibility test.
- **Consequences**: Done once in this PR: re-run twice with the uv environment, every number identical to F0 (E-010). A smaller image without Jupyter or matplotlib.

<a id="d-025"></a>
### D-025 Docker base image: `python:3.12-slim`, two stages, pinned by digest, non-root

Date: 2026-11-22 · Step: 1.2 · Status: Active

- **Context**: The base image decides size, available binaries and attack surface.
- **Decision**: `python:3.12.16-slim-trixie` pinned by version **and digest**. Two stages: `builder` installs the locked dependencies with uv; `runtime` copies only the environment. The container runs as an unprivileged user (uid 10001). uv comes from the `astral/uv` image, also pinned by digest.
- **Alternatives considered**: `python:3.12` full (about 1 GB); `alpine` (musl: no wheels for numpy, scipy, lightgbm, everything compiles); distroless (no shell, hard to debug)
- **Why**: slim has what scientific wheels need and little else. A digest identifies an exact image: the image that passed CI is the one that runs in AWS, byte for byte. A non-root user limits what an attacker can do after exploiting a bug.
- **Consequences**: Base images need updating for security patches: Dependabot proposes new digests weekly (D-029). Measured size 211 MB.

<a id="d-026"></a>
### D-026 Minimal image now, plus a test stage

Date: 2026-11-22 · Step: 1.2 · Status: Active

- **Context**: The playbook asks for a Dockerfile in step 1.2, but there is nothing to run until F3 (training) and F5 (API).
- **Decision**: The image holds the installed package and its default command prints the version. A `test` stage (never shipped) installs the dev tools, deletes `src/` and runs the unit tests against the installed package.
- **Alternatives considered**: Wait until F3
- **Why**: The full chain (code, package, image, tests, CI) works from day one; each phase then only adds pieces. Packaging errors appear in the PR that causes them, not all at once in F3.
- **Consequences**: Training and API will likely be separate final stages of the same Dockerfile, sharing base and common layers; decided in F3 and F5 with sizes in hand.

<a id="d-027"></a>
### D-027 docker compose holds only Postgres 18 for now

Date: 2026-11-22 · Step: 1.2 · Status: Active

- **Context**: Postgres will store the loans arriving in the simulation, every API prediction (D-008, also an EU AI Act record-keeping duty for high-risk systems), labels and monitoring metrics.
- **Decision**: Only **Postgres 18.7** in compose, with a named volume, a healthcheck and credentials from `.env`. MLflow enters in F3, the API in F5, Grafana in F6, each with its tests. The port is bound to localhost only. Driver: **psycopg 3** (whether to add SQLAlchemy is decided in F2).
- **Alternatives considered**: Every service from day one, even if empty
- **Why**: Every service in the repository has a use and a test, same logic as no empty folders (D-021). Postgres 18 is the newest major version offered by AWS RDS (since November 2025), so development and production match.
- **Consequences**: The Postgres 18 image stores data in `/var/lib/postgresql/18/docker`, so the volume is mounted on `/var/lib/postgresql` (E-009). Test B3 fails if the major version changes; Dependabot is told not to propose major Postgres updates.

<a id="d-028"></a>
### D-028 CI: four parallel jobs on every PR and push to main

Date: 2026-11-22 · Step: 1.3 · Status: Active

- **Context**: Nothing should reach `main` without passing the checks, and a slow CI gets skipped.
- **Decision**: GitHub Actions workflow `ci.yml`, four jobs in parallel: **quality** (ruff, format, mypy, `uv lock --check`); **tests** (unit tests with branch coverage); **secrets** (gitleaks over the full history); **integration** (build the image, unit tests inside it, start Postgres, tests B3 to B5, destructive B4 last). Runs on every PR and every push to `main`.
- **Alternatives considered**: Jobs in sequence; running notebooks on every PR
- **Why**: Parallel jobs take as long as the slowest one and show every failure at once. `main` is checked again after merging because two PRs that pass separately can break together. Target under 5 minutes, with uv and Docker layer caches.
- **Consequences**: Notebook execution needs the 1.6 GB data and is decided in F2 (probably a small sample per PR, the full data in a scheduled run). Changes to workflows, pre-commit or test configuration are flagged in every PR description, since a PR can weaken its own CI.

<a id="d-029"></a>
### D-029 Scheduled security scans and Dependabot

Date: 2026-11-22 · Step: 1.3 · Status: Active

- **Context**: Vulnerabilities are published without any change in our code.
- **Decision**: Workflow `security.yml`: **pip-audit** over every locked dependency (all groups) every Monday and on every PR that changes `uv.lock`; **Trivy** over the image every Monday, failing on HIGH or CRITICAL. Trivy exceptions live in `.trivyignore.yaml`, each with a reason and an expiry date. **Dependabot** weekly for uv, Docker, docker compose and GitHub Actions; minor and patch updates grouped per ecosystem, majors one by one.
- **Alternatives considered**: No Dependabot (manual updates); Renovate; Grype or Docker Scout instead of Trivy
- **Why**: Scheduled scans catch new vulnerabilities in unchanged code. Dependabot only proposes; the CI tests whether our system still works with the new version, so a green PR is worth as much as the tests behind it.
- **Consequences**: Juan reviews and merges Dependabot PRs. A finding with no fix gets an exception that expires, so it is reviewed again instead of ignored forever. First scan: 13 HIGH findings in Debian base packages, 12 without a fix, 1 fixed in Debian but not yet in the official image (D-038).

<a id="d-030"></a>
### D-030 Actions pinned by commit hash; workflows read-only

Date: 2026-11-22 · Step: 1.3 · Status: Active

- **Context**: A workflow runs third-party actions with access to the code and the CI secrets. A tag like `v6` can be moved; in March 2025 the tags of `tj-actions/changed-files` were moved to code that dumped CI secrets into logs.
- **Decision**: Every action pinned by commit hash with its version in a comment; Docker images used by CI pinned by digest. Every workflow declares `permissions: contents: read`.
- **Alternatives considered**: Pin by tag
- **Why**: A commit hash cannot be moved. Same rule as the lock hashes (D-019) and image digests (D-025): everything that comes from outside is pinned by its fingerprint. Least privilege limits the damage of a compromised action.
- **Consequences**: Dependabot updates the hashes. Files are slightly harder to read, hence the version comment.

<a id="d-031"></a>
### D-031 Coverage measured with branches; minimum set in F2

Date: 2026-11-22 · Step: 1.3 · Status: Active

- **Context**: Coverage shows untested code but does not prove tests check anything (Goodhart's law).
- **Decision**: Branch coverage is measured and shown in every CI run, with **no minimum until F2**. Proposal for F2: a high minimum on `src/` (around 85 to 90% with branches) and no PR may lower coverage.
- **Alternatives considered**: A 90% minimum now; never a minimum
- **Why**: With two small files any threshold is trivial or arbitrary. Juan approving every test is the real defence against tests that execute lines without checking results.
- **Consequences**: The threshold is decided in F2 on real code.

<a id="d-032"></a>
### D-032 Branch protection of `main`, no bypass, no required approval

Date: 2026-11-22 · Step: 1.3 · Status: Active

- **Context**: Without rules nothing stops a merge with red CI or a direct push to `main`.
- **Decision**: A GitHub ruleset on `main`: PR required; the four CI jobs required; branch up to date with `main`; conversations resolved; no force push or deletion; **no bypass, not even for the administrator**. Set up by Juan once the CI has run (GitHub only lists checks that have run).
- **Alternatives considered**: Allow the administrator to bypass
- **Why**: A rule with an exception for the administrator ends up used in a hurry.
- **Consequences**: **Adaptation for a one-person project**: "require one approval" is not enabled. PRs are opened with Juan's account and GitHub does not let an author approve their own PR, so it would block every merge. Juan's merge is the review. In a team at least one approval would be required.

<a id="d-033"></a>
### D-033 Decision log format: index plus one card per decision

Date: 2026-11-22 · Step: 1.4 · Status: Active

- **Context**: The log was a six-column table with cells of over 100 words, unreadable on a phone and growing towards 60 to 80 decisions.
- **Decision**: One file: a short index table (ID, date, step, decision in one line, status), then one card per decision with Context, Decision, Alternatives, Why, Consequences and Status. A decision is never deleted or rewritten: a new one supersedes it and the old one is marked.
- **Alternatives considered**: Keep the table; classic ADR, one file per decision in `docs/adr/`
- **Why**: Readable on any screen, one file to search, direct links to each card. The history of changes of mind stays visible.
- **Consequences**: D-001 to D-018 were converted with their text unchanged; they were recorded before the card format, so they have no separate Context and Consequences.

<a id="d-034"></a>
### D-034 Error log format; F0 errors moved into it

Date: 2026-11-22 · Step: 1.4 · Status: Active

- **Context**: Errors were recorded inside the audit document; a log of errors is needed for the whole project.
- **Decision**: `docs/errors.md`: index plus one card per error with Symptom, Cause, Fix and **Prevention**, which whenever possible is an automatic test or check, not "be careful". The seven audit errors move there as E-001 to E-007, with their prevention added.
- **Alternatives considered**: Same format, keep the F0 errors in `data_audit.md`
- **Why**: One place for every error. Blameless postmortem idea: what was missing in the system for this to happen.
- **Consequences**: `data_audit.md` section 8 now links to the log.

<a id="d-035"></a>
### D-035 README as showcase, `docs/technical.md` as manual

Date: 2026-11-22 · Step: 1.4 · Status: Active

- **Context**: A reader of the README (recruiter, interviewer) gives it 1 to 3 minutes; a technical reviewer or a new thread needs every detail.
- **Decision**: README in nine parts: what it is (with live CI badge), authorship, problem, architecture, results, key decisions grouped by theme (framing, no leakage, fairness, architecture, engineering, modelling), how to run it, status by phase, repository map. `docs/technical.md`: tracking sheet plus one section per playbook step.
- **Alternatives considered**: One long README; a minimal README
- **Why**: Each document serves its reader. Key decisions are grouped by theme so that 30 seconds cover business, data, ethics, architecture, engineering and model (Juan: design, tests and CI matter most now, modelling later).
- **Consequences**: Every PR updates `technical.md` and the tracking sheet; the README only when something visible changes. The "how to run" commands are the ones checked on a clean clone.

<a id="d-036"></a>
### D-036 Repository documents in English

Date: 2026-11-22 · Step: 1.4 · Status: Active

- **Decision**: Everything in the repository is written in English; the conversation with Juan is in Spanish.
- **Alternatives considered**: Spanish
- **Why**: The readers of the repository (interviewers, international teams) read English. Same as F0.

<a id="d-037"></a>
### D-037 Work branch named by the system

Date: 2026-11-22 · Step: 1.1 · Status: Active

- **Context**: `forma_de_trabajo.md` names branches `fase-N/description`.
- **Decision**: F1 is developed on `claude/project-thread-akqyz1`, the branch assigned by the working environment, as in F0.
- **Alternatives considered**: `fase-1/cimientos`
- **Why**: The cloud environment only allows pushing to the branch it assigns to the thread.
- **Consequences**: The branch name does not appear in `main`; the PR title says the phase.

<a id="d-038"></a>
### D-038 Base image patch not yet published upstream: wait for the official image

Date: 2026-11-22 · Step: 1.3 · Status: Active

- **Context**: the first Trivy scan found CVE-2026-85091 (zlib, HIGH) fixed in Debian 13 but not yet in the official `python:3.12-slim` image.
- **Decision**: wait for the official image to be rebuilt. The finding is listed in `.trivyignore.yaml` with a 14-day expiry (2026-12-06); Dependabot proposes the new digest when it exists. If it is still unfixed at expiry, the weekly scan fails and this is reconsidered.
- **Alternatives considered**: upgrade the affected packages in the Dockerfile (`apt-get install --only-upgrade`), which patches immediately but makes the build depend on the state of the Debian mirrors on the day it runs, so two builds of the same commit can differ.
- **Why**: keeps the build reproducible (D-025), and nothing is deployed until F7, so the exposure is nil.
- **Consequences**: if this happened with the API in production, the balance would change and the package would be patched in the Dockerfile at once.

<a id="d-039"></a>
### D-039 Simulated arrival: listings and outcomes as two separate streams

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: the source is a single 2019 snapshot in which every row already holds its final outcome. The system must behave as if it lived at a simulated date T and knew only what was known at T.
- **Decision**: each loan produces two facts at two dates. Ingesting a period loads (1) the **listings** published in that month, with only the columns visible at listing, and (2) the **outcomes** of loans resolved in that month (resolution month as estimated in the audit, section 4.2), into separate tables. At date T the database holds exactly what was known at T. Loans still running at the snapshot never produce an outcome. The original file is kept untouched with its SHA-256.
- **Alternatives considered**: one table with the full row (151 columns) loaded by issue month, and every query filtering "resolved before T".
- **Why**: with separate streams, future information is not in the database, so leakage is impossible by construction instead of depending on every query being written correctly. It also mirrors how the data arrives in reality.
- **Consequences**: two tables and two loads per period; the split of columns between the streams follows D-014. Recovery amounts are as of 2019 (limitation already accepted in D-017).
