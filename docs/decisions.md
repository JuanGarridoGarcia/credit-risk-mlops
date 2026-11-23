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
| [D-040](#d-040) | 2026-11-23 | 2.3 (audit 9.4) | Training labels: matured cohorts only | Active |
| [D-041](#d-041) | 2026-11-23 | 2.1 (audit 9.5) | Simulation window: first training 2014-01, replay 2014-01 to 2018-12 | Active |
| [D-042](#d-042) | 2026-11-23 | 2.3 (audit 9.6) | Validation split: out-of-time, last 6 listing months | Active |
| [D-043](#d-043) | 2026-11-23 | 2.1 | A separate simulator is the only code that reads the 2019 file | Active |
| [D-044](#d-044) | 2026-11-23 | 2.1 | Two table layers: raw (text as delivered) and clean (typed) | Active |
| [D-045](#d-045) | 2026-11-23 | 2.1 | Cleaning in one Python module; batch-only logic in SQL | Active |
| [D-046](#d-046) | 2026-11-23 | 2.1 | polars in system code; conversion only at the model boundary | Active |
| [D-047](#d-047) | 2026-11-23 | 2.1 | Database access: psycopg 3 with SQL in `.sql` files, `COPY` for bulk loads | Active |
| [D-048](#d-048) | 2026-11-23 | 2.1 | Schema migrations with dbmate, plain SQL, never edited once merged | Active |
| [D-049](#d-049) | 2026-11-23 | 2.1 | Idempotent loads: replace the whole period in one transaction, plus a load log | Active |
| [D-050](#d-050) | 2026-11-23 | 2.1 | Deliveries written as gzip-compressed CSV, all text | Active |
| [D-051](#d-051) | 2026-11-23 | 2.1 | Cleaning is minimal and has no opinions | Active |
| [D-052](#d-052) | 2026-11-23 | 2.1 | Image size budget raised from 300 to 500 MB | Active |

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

<a id="d-040"></a>
### D-040 Training labels: matured cohorts only

Date: 2026-11-23 · Step: 2.3 (audit decision 9.4, decided before 9.5 because the window depends on it) · Status: Active

- **Context**: at a simulated date T, loans listed recently are only partly resolved, and the ones already resolved are mostly early defaults (censoring bias).
- **Decision**: a PD training set at date T uses only **matured cohorts**: loans listed at least `term + 5` months before T (41 months for 36-month loans, 65 for 60-month loans), whose outcome is fully known. The 5 months cover the charge-off lag (audit, section 4.2). A survival model, which would also use running loans as partial information, is noted as a possible challenger in F3.
- **Alternatives considered**: every loan resolved by T ("known by T"); a survival model from the start.
- **Why**: "known by T" shows a bad rate of 17% to 18% against 11% to 13% for complete cohorts (audit, section 6.2). The PD feeds expected loss (D-002), so a systematically inflated PD would distort EL and the buy decision. A survival model is more correct in theory but harder to calibrate and explain, and does not match the logistic baseline (D-004).
- **Consequences**: training data is older and smaller (the model reacts slower to market changes, which F6 monitoring must catch). Updates `problem.md` section 7. The LGD rule stays D-017.

<a id="d-041"></a>
### D-041 Simulation window: first training 2014-01, replay 2014-01 to 2018-12

Date: 2026-11-23 · Step: 2.1 (audit decision 9.5) · Status: Active

- **Context**: an earlier first training gives a weaker first model but a longer life of the system; a later one gives a better first model but little to replay and nothing measurable at the end.
- **Decision**: first training at **T0 = 2014-01**; monthly replay from 2014-01 to 2018-12. Loans listed before T0 are loaded as history before the replay starts.
- **Alternatives considered**: T0 = 2015-01 (23,358 matured loans, final business metric only for 2015); T0 = 2016-01 (53,682 matured loans, no purchase with a final outcome).
- **Why**: 2.03 million loans replayed and five years of monitoring and retraining. The business metric (D-007) is final for 36-month loans listed in 2014 and 2015 (outcomes in the 2019 snapshot). The first model has 12,078 matured loans with 1,457 defaults (checked on the raw file on 2026-11-23), enough for a logistic regression with about 70 parameters (10 to 20 defaults per parameter).
- **Consequences**: the first model learns from 36-month loans listed 2007-06 to 2010-08 (post-crisis), so it is weak and the system must visibly improve through retraining and new fields (D-016). Bureau fields reported from 2012 cannot enter the first model.

<a id="d-042"></a>
### D-042 Validation split: out-of-time, last 6 listing months

Date: 2026-11-23 · Step: 2.3 (audit decision 9.6) · Status: Active

- **Context**: the validation set is where everything the model does not learn by itself is chosen (hyperparameters, early stopping, candidate comparison, calibration, buy threshold, metric noise). The test is the forward replay (D-041), which does not exist yet at training time.
- **Decision**: at every training, the **last 6 listing months** of the matured cohorts (D-040) are the validation set; the earlier months are the training set. First model: train 7,745 loans (2007-06 to 2010-02), validation 4,333 loans with 432 defaults (2010-03 to 2010-08). Metric noise is measured by bootstrap on the validation set.
- **Alternatives considered**: random 20% split; rolling-origin validation (several time windows averaged).
- **Why**: it mimics production (learn from the past, predict an unseen future). A random split mixes vintages while the bad rate falls from 18% (2007) to 10% (2010), so it would be optimistic and hide drift. Rolling-origin is more robust with little data, but its first windows have very few defaults (292 in 2007 and 2008) and later retrainings have hundreds of thousands of loans, so it does not pay for its complexity.
- **Consequences**: nothing that learns or chooses anything (model, calibrator, threshold) may touch the test. Deferred to F3 with the calibration design: whether to refit on the full matured set after selection (the calibrator fitted on validation would no longer match the refitted model) and whether to split validation into a selection part and a calibration part once data is large.

<a id="d-043"></a>
### D-043 A separate simulator is the only code that reads the 2019 file

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: D-039 keeps the future out of the database; it still has to be decided where the cut between "known" and "not yet known" is made.
- **Decision**: a separate module, the **simulator**, plays the role of Lending Club. It is the only code that opens the 2019 file. For each month it writes two deliveries, `listings` and `outcomes`, into a landing folder, as an external provider would. The system (ingestion, validation, features, model) only reads deliveries of months that have already "arrived" and never opens the full file. A test checks that system code does not import the simulator or read the file's path.
- **Alternatives considered**: ingestion opens the full file on every run and filters the month.
- **Why**: it separates the simulated world, which would not exist in production, from the system, which would. The system cannot filter the future wrongly because it never receives it. If a real source replaced the file, only the simulator would be thrown away; ingestion would not change.
- **Consequences**: one more module and disk space for the deliveries. Deliveries keep the text exactly as in the file.

<a id="d-044"></a>
### D-044 Two table layers: raw (text as delivered) and clean (typed)

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: deliveries arrive as text with formats and codes that are not usable as they are (`" 36 months"`, `"10+ years"`, `dti = 999`). The playbook requires the raw data to be stored as it is.
- **Decision**: each stream (`listings`, `outcomes`) has a **raw** table with the exact text of the delivery plus load metadata (period, delivery file, its hash, load time), never modified after loading, and a **clean** table with correct types and coded values fixed. Validation (step 2.2) runs between the two: if a critical rule fails, nothing reaches the clean layer. Cleaning only puts the data in the form it should have arrived in; feature engineering (step 2.4) starts from the clean layer. The unit of load is the month, because `issue_d` has monthly precision.
- **Alternatives considered**: clean layer only (convert at load, discard the text); raw layer only (convert in Python on every read).
- **Why**: if a cleaning rule turns out to be wrong, the rule is fixed and the clean layer is rebuilt from raw without reloading anything, and "what exactly arrived?" can always be answered. Standard pattern (often called bronze and silver).
- **Consequences**: about twice the storage. The API must clean each incoming listing with the same code as the clean layer, which constrains where cleaning is written (next decision).

<a id="d-045"></a>
### D-045 Cleaning in one Python module; batch-only logic in SQL

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: cleaning runs in two places: in batch (each month, raw to clean) and online (the API cleans each incoming listing before predicting, within the 200 ms budget of D-009). Two implementations of the same rule drift apart and cause training-serving skew, a silent failure (the model receives in production data it never saw in training).
- **Decision**: cleaning is written **once, in Python**, as functions that work the same on a month of rows and on a single row. The monthly load and the API call the same functions. General line for the project: what also happens at prediction time (cleaning, features) is in Python, with a single implementation; what exists only in batch is in SQL: the schema and its constraints, idempotent loads, part of the validation, labels and the training set at date T (step 2.3), and monitoring aggregates (F6).
- **Alternatives considered**: SQL or dbt inside Postgres (fast in batch, but the API would need a second implementation in Python); hybrid dbt for batch plus Python for the API with a test that both agree.
- **Why**: it meets the playbook rule "no second implementation of anything" without workarounds. Juan wants to show SQL; the batch-only pieces give real SQL work with no risk of two versions.
- **Consequences**: data leaves Postgres and comes back on each clean load (2 million rows in total, acceptable). dbt is not used for cleaning; it may be considered for F6 monitoring.

<a id="d-046"></a>
### D-046 polars in system code; conversion only at the model boundary

Date: 2026-11-23 · Step: 2.1 (open question from D-024) · Status: Active

- **Context**: the simulator, cleaning and features need a dataframe library. The same cleaning code serves a month in batch and a single row in the API (D-045).
- **Decision**: **polars** in all system code. Where a modelling library needs pandas or numpy, the conversion happens in **one function at the model input** and nowhere else. pandas does not appear elsewhere in the code.
- **Alternatives considered**: pandas.
- **Why**: polars is strict with types: a value that cannot be converted fails instead of silently becoming missing (fail fast), so every conversion follows a rule written by us and tested both ways. It is faster in batch (the simulator reads 2.26 million rows) and the F0 audit is already in polars. Measured on 2026-11-23 for a sample cleaning of one row (the API case): polars 0.3 ms, pandas 1.4 ms, both far below the 200 ms budget, so speed online does not decide. scikit-learn 1.9.1 accepts polars input directly (checked).
- **Consequences**: SHAP, tree libraries or MLflow signatures may need a conversion; checked library by library in F3. Lenient options (`strict=False`) are not used in cleaning.

<a id="d-047"></a>
### D-047 Database access: psycopg 3 with SQL in `.sql` files, `COPY` for bulk loads

Date: 2026-11-23 · Step: 2.1 (open question from D-021/B3) · Status: Active

- **Context**: psycopg 3 is already used since F1. The question was whether to add SQLAlchemy on top.
- **Decision**: Python talks to Postgres with **psycopg 3** directly. SQL lives in `.sql` files, written as it runs. Bulk loads use `COPY`. Values always travel as **parameters** (`%s`), never pasted into the SQL text; table and column names are composed with `psycopg.sql.Identifier`. A connection pool (`psycopg-pool`) is added for the API in F5.
- **Alternatives considered**: SQLAlchemy Core (builds SQL from Python, manages connections, portable across databases); SQLAlchemy ORM (tables as classes, rows as objects).
- **Why**: full transparency of the SQL (Juan wants to show SQL, D-045) and the fastest load path, with a dependency already in use. Portability brings almost nothing: the database is Postgres from start to end (local and RDS, D-027). The ORM suits web apps working with single objects, not month-sized tables.
- **Consequences**: some things SQLAlchemy gives for free are written by hand or added explicitly (connection pool). Parameters prevent SQL injection, a real risk here because `emp_title`, `title` and `desc` are free text written by applicants and the API will receive outside data; ruff rule `S608` flags SQL built from strings. The speed gain of `COPY` over row-by-row `INSERT` is measured during implementation.

<a id="d-048"></a>
### D-048 Schema migrations with dbmate, plain SQL, never edited once merged

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: tables are created now and will change (prediction log in F5, monitoring in F6, late-starting fields from D-016). Once there is data that must not be lost (RDS in F7), the schema cannot be dropped and recreated.
- **Decision**: schema changes are **numbered migrations in plain SQL** (`-- migrate:up` / `-- migrate:down`), applied with **dbmate** run from its Docker image (pinned by digest, as D-025). dbmate records applied versions in `schema_migrations`, so `dbmate up` brings any database (laptop, CI, RDS) to the same schema by applying only what is missing, in order. A migration merged into `main` is **never edited**; a fix is a new migration. A test applies every migration on an empty database, rolls them all back and applies them again.
- **Alternatives considered**: Alembic (Python standard, but built around SQLAlchemy and its main advantage, autogenerating from ORM models, does not apply without an ORM, D-047); a small in-house runner (no dependency, but our own code to test and maintain); no migrations, a `schema.sql` dropped and recreated (stops working once data must be kept).
- **Why**: plain SQL in view, consistent with D-047; a proven, widely used tool; reproducible across environments. Checked on 2026-11-23 that dbmate 2.38.2 runs on the work machine.
- **Consequences**: one more tool run through Docker. Editing an applied migration would leave databases with the same recorded history and different schemas, which is why the rule exists. `down` parts are for development; in production the schema is fixed forward.

<a id="d-049"></a>
### D-049 Idempotent loads: replace the whole period in one transaction, plus a load log

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: loads are repeated in practice (network failure halfway, a relaunched command, a corrected delivery). If a repetition duplicates rows, the model learns from loans counted twice without anyone noticing.
- **Decision**: loading a period of a stream **deletes that period and loads the delivery with `COPY` inside one transaction**: either the whole month is replaced or nothing changes. A table `ingest_log` records each load: period, stream, SHA-256 of the delivery file, rows in the file, rows loaded, time and result. The same file (same hash) already loaded is a no-op recorded as "unchanged"; a different file replaces the period and the change is recorded. Rows loaded must equal rows in the file. Same mechanism for the raw and clean layers.
- **Alternatives considered**: upsert row by row (`INSERT ... ON CONFLICT DO UPDATE`), which leaves behind rows removed from a corrected delivery and is slower; skip a period already loaded, which never applies a corrected delivery unless forced by hand.
- **Why**: atomic, fast with `COPY`, and correct with corrected deliveries. The log gives traceability and the row count check the playbook asks for. The largest month (2016-03) has 61,992 loans, so rewriting a whole month costs nothing.
- **Consequences**: readers never see a half-loaded month: until the commit they see the old version, after it the new one (Postgres MVCC).

<a id="d-050"></a>
### D-050 Deliveries written as gzip-compressed CSV, all text

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: the simulator (D-043) writes one `listings` and one `outcomes` delivery per month.
- **Decision**: deliveries are **gzip-compressed CSV** files with every value as text, exactly as in the source file.
- **Alternatives considered**: Parquet (typed, columnar, smaller and faster).
- **Why**: it is the format Lending Club published, so "store the raw data as it is" (D-044) is literal; Postgres `COPY` reads CSV natively; the files can be opened with any tool. With Parquet the simulator would either write types, which is cleaning and belongs to the system (D-045), or write everything as text and lose Parquet's main advantage.
- **Consequences**: larger and slower to read than Parquet, irrelevant at the size of a month. A change of format in a column is caught by validation on the raw layer (step 2.2), with strict cleaning (D-046) as a second net.

<a id="d-051"></a>
### D-051 Cleaning is minimal and has no opinions

Date: 2026-11-23 · Step: 2.1 · Status: Active

- **Context**: without a boundary, cleaning grows and ends up taking hidden modelling decisions (for example, capping `dti` at 100 would hide 2,561 loans from anyone reading the model code). The clean layer serves the PD model, the LGD model and monitoring alike.
- **Decision**: cleaning may only (1) **convert types** (text to number, `Dec-2015` to a date), (2) **normalise documented formats** (`" 36 months"` to 36, `"10+ years"` to 10, `"< 1 year"` to 0) and (3) **decode values that Lending Club documents as "unknown"**. It never removes rows, fills missing values, caps extremes, merges categories or creates features: that is modelling, done in step 2.4 with its own reasons. Impossible or suspicious values are not fixed by cleaning; validation (step 2.2) detects them and decides whether to stop or warn.
- **Alternatives considered**: broad cleaning that also merges rare categories, caps extremes and fills simple gaps, so the clean layer is ready to model.
- **Why**: the clean layer stays "the data as it should have arrived", useful for every purpose and easy to audit; every modelling decision is visible where it is taken.
- **Consequences**: more work in step 2.4. Applying the rule already changed a proposal of the audit: `dti = 999` is not documented as unknown and turned out to be a cap caused by implausible incomes (E-014), so it stays as it is; `annual_inc = 0` is a real value of joint applications. Both become validation rules.

<a id="d-052"></a>
### D-052 Image size budget raised from 300 to 500 MB

Date: 2026-11-23 · Step: 2.1 (changes the threshold of test B5, D-025/D-026) · Status: Active

- **Context**: with polars in the package (D-046), the image grew from 211 MB to 456 MB and test B5 (at most 300 MB) failed. polars' compiled runtime alone takes 170 MB. The API needs polars to clean with the same code as the monthly load (D-045).
- **Decision**: the budget of B5 becomes **500 MB**.
- **Alternatives considered**: keep 300 MB and clean with pandas in the API (two implementations, against D-045); keep 300 MB with two images, one for loading with polars and one for the API without it (same two implementations, plus another image).
- **Why**: the size follows from a decision already taken; breaking the single-implementation rule to save 150 MB does not pay. 456 MB is a normal size for an ML service, and scikit-learn and model libraries will enter in F3 and F5.
- **Consequences**: B5 still catches anything that should not be in the image. The budget is reviewed when the model libraries enter.
