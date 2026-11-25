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
| [D-042](#d-042) | 2026-11-23 | 2.3 (audit 9.6) | Validation split: out-of-time, last 6 listing months | Superseded by D-069 |
| [D-043](#d-043) | 2026-11-23 | 2.1 | A separate simulator is the only code that reads the 2019 file | Active |
| [D-044](#d-044) | 2026-11-23 | 2.1 | Two table layers: raw (text as delivered) and clean (typed) | Active |
| [D-045](#d-045) | 2026-11-23 | 2.1 | Cleaning in one Python module; batch-only logic in SQL | Active |
| [D-046](#d-046) | 2026-11-23 | 2.1 | polars in system code; conversion only at the model boundary | Active |
| [D-047](#d-047) | 2026-11-23 | 2.1 | Database access: psycopg 3 with SQL in `.sql` files, `COPY` for bulk loads | Active |
| [D-048](#d-048) | 2026-11-23 | 2.1 | Schema migrations with dbmate, plain SQL, never edited once merged | Active |
| [D-049](#d-049) | 2026-11-23 | 2.1 | Idempotent loads: replace the whole period in one transaction, plus a load log | Active |
| [D-050](#d-050) | 2026-11-23 | 2.1 | Deliveries written as gzip-compressed CSV, all text | Active |
| [D-051](#d-051) | 2026-11-23 | 2.1 | Cleaning is minimal and has no opinions | Active |
| [D-052](#d-052) | 2026-11-23 | 2.1 | Image size budget raised from 300 to 500 MB | Superseded by D-078 |
| [D-053](#d-053) | 2026-11-23 | 2.2 | Validation rules written with pandera on polars | Active |
| [D-054](#d-054) | 2026-11-23 | 2.2 | Two severity levels: a critical rule stops the run, a warning is reported and stored | Active |
| [D-055](#d-055) | 2026-11-23 | 2.2 | A critical failure stops the whole month; no row quarantine | Active |
| [D-056](#d-056) | 2026-11-23 | 2.2 | Allowed values come from a dated contract: the 2013-12 base plus dated changes | Active |
| [D-057](#d-057) | 2026-11-23 | 2.2 | Every test is listed in a catalogue kept in step with the code by a test | Active |
| [D-058](#d-058) | 2026-11-23 | 2.3 | A training set version is an immutable snapshot plus a manifest of where it came from | Active |
| [D-059](#d-059) | 2026-11-23 | 2.3 | Snapshots in object storage by content hash; manifests in Postgres | Active |
| [D-060](#d-060) | 2026-11-23 | 2.3 | A snapshot is two files: what training may see, and what only evaluation may see | Active |
| [D-061](#d-061) | 2026-11-23 | 2.3 | Two hashes: the content hash names a version, the file checksum guards the stored file | Active |
| [D-062](#d-062) | 2026-11-23 | 2.4 | Two layers of preparation: fixed transformations in the package, learned ones inside the model | Active |
| [D-063](#d-063) | 2026-11-23 | 2.4 | v1 features: the columns filled since 2007 plus two required transformations; engineered features are F3 experiments | Active |
| [D-064](#d-064) | 2026-11-23 | F2 (cross-cutting) | Coverage: 85% of branches over unit and integration tests, 90% of the lines each pull request changes | Active |
| [D-065](#d-065) | 2026-11-23 | F2 (cross-cutting) | The audit notebook runs in CI every week and on pull requests that touch it, and must reproduce its outputs | Active |
| [D-066](#d-066) | 2026-11-23 | F3 (cross-cutting) | uv, the uv_build backend and the uv Docker image move together, to 0.13.9 | Active |
| [D-067](#d-067) | 2026-11-23 | 3.1 | F3 fixes a training procedure, not a model, using only data available at T0 | Active |
| [D-068](#d-068) | 2026-11-23 | 3.2 | PD candidates: logistic regression and one gradient boosting model; within the noise, the simpler wins | Active |
| [D-069](#d-069) | 2026-11-23 | 3.1 | Validation split per term: the last 6 matured listing months of each term | Active |
| [D-070](#d-070) | 2026-11-23 | 3.1 | Coverage rule: a term is scored only with at least 200 defaults in its training and 200 in its validation | Active |
| [D-071](#d-071) | 2026-11-23 | 3.2 | `installment` never enters; a recomputed instalment and its ratio to income are F3 experiments | Active |
| [D-072](#d-072) | 2026-11-23 | 3.2 | The gradient boosting candidate is LightGBM | Active |
| [D-073](#d-073) | 2026-11-23 | 3.2 | Hyperparameters are tuned on an inner time split of the training set; validation stays clean | Active |
| [D-074](#d-074) | 2026-11-23 | 3.2 | Search: Optuna TPE with 50 seeded trials for LightGBM, a grid over `C` for the logistic regression | Active |
| [D-075](#d-075) | 2026-11-23 | 3.2 | "Better by more than the noise": the 95% paired bootstrap interval of the difference lies above zero | Active |
| [D-076](#d-076) | 2026-11-23 | 3.2 | The PD is calibrated with Platt scaling fitted on the validation set | Active |
| [D-077](#d-077) | 2026-11-23 | 3.2 | No refit on training plus validation: the deployed model is exactly the one measured | Active |
| [D-078](#d-078) | 2026-11-23 | 3.2 | Two images from one Dockerfile: `serve` (budget 800 MB) and `train` (budget 1.5 GB) | Active |
| [D-079](#d-079) | 2026-11-23 | 3.2 | Tracking: an MLflow server in docker compose, metadata in its own Postgres database, artefacts in object storage | Active |
| [D-080](#d-080) | 2026-11-23 | 3.3 | Monotone constraints on nine features with an undisputed direction; sign test for the logistic regression | Active |
| [D-081](#d-081) | 2026-11-23 | 3.3 | Key segments: grade, covered term and listing quarter; a new model fails if it is clearly worse in any of them | Active |
| [D-082](#d-082) | 2026-11-23 | 3.4 | Automatic promotion when every rule passes, with evidence, an alert and a tested rollback | Active |
| [D-083](#d-083) | 2026-11-23 | 3.5 | The API returns the four main reasons of each prediction; the full SHAP vector is stored with it | Active |
| [D-084](#d-084) | 2026-11-24 | 3.x (buy rule, open since problem.md) | Buy rule: buy when the expected return beats a minimum chosen on validation | Active |
| [D-085](#d-085) | 2026-11-24 | 3.x (buy rule) | Budget: one 25 dollar note per loan, a monthly cap of 10% of last month's listings, idle cash earns nothing | Active |
| [D-086](#d-086) | 2026-11-24 | 3.3 | Behavioural model tests: invariance, direction, minimum cases, prediction time, and bad models that must fail | Active |
| [D-087](#d-087) | 2026-11-24 | 3.2 | LGD candidates: regularised linear regression and LightGBM against the mean by grade, with the PD machinery | Active |
| [D-088](#d-088) | 2026-11-24 | 3.2 (changes step 2.3) | The LGD label is a column of the training file, computed when the snapshot is built | Active |
| [D-089](#d-089) | 2026-11-24 | F3 (cross-cutting) | F3 is delivered in three pull requests: data, training, explanation and business | Active |
| [D-090](#d-090) | 2026-11-24 | 3.4 | With no PD champion yet, the first model must beat the grade-only baseline; otherwise the baseline is the champion | Active |
| [D-091](#d-091) | 2026-11-24 | 3.2 | The MLflow server of docker compose runs from our `train` image | Active |
| [D-092](#d-092) | 2026-11-24 | 3.2 | The logistic regression keeps the signs of D-080 by removing a wrong-signed feature and refitting | Active |
| [D-093](#d-093) | 2026-11-24 | 3.3 | A key segment blocks a promotion only if it is clearly worse by more than a margin | Active |
| [D-094](#d-094) | 2026-11-24 | 3.2 | The level of every LGD model is corrected on validation, like Platt scaling for the PD | Active |
| [D-095](#d-095) | 2026-11-24 | 3.5 | A model card is generated for every registered version and stored with it | Active |
| [D-096](#d-096) | 2026-11-24 | 3.5 | The realised return is measured on the 12 months after T0; validation only chooses the minimum of the buy rule | Active |
| [D-097](#d-097) | 2026-11-24 | 3.5 | The business result at T0 is reported as measured; improving the buy rule is a later decision | Active |
| [D-098](#d-098) | 2026-11-24 | F4 | Scope of F4: the orchestrated training flow and a simulated clock; batch prediction (step 4.2) moves to F5 | Active |
| [D-099](#d-099) | 2026-11-24 | 4.1 | Orchestrator: Prefect 3 | Active |
| [D-100](#d-100) | 2026-11-24 | 4.1 | Tasks are cut where their result is stored; only identifiers travel between them; PD and LGD apart | Active (amended by D-105) |
| [D-101](#d-101) | 2026-11-24 | 4.1 | Training is idempotent by a key kept in MLflow: model, training set version and code commit | Active |
| [D-102](#d-102) | 2026-11-24 | 4.1 | Only transient failures are retried: 3 attempts after 10, 30 and 90 seconds | Active |
| [D-103](#d-103) | 2026-11-24 | 4.1 | Prefect in the `train` group, accepting three version downgrades; server and worker from the `train` image | Active |
| [D-104](#d-104) | 2026-11-24 | 4.1 | The load task catches up every delivered month up to the one asked | Active |
| [D-105](#d-105) | 2026-11-24 | 4.1 | Publishing deliveries is not a task of the system's flow (D-043 kept) | Active |
| [D-106](#d-106) | 2026-11-24 | 4.1 | Retraining every quarter (January, April, July, October); every month is loaded | Active |
| [D-107](#d-107) | 2026-11-24 | 4.1 | The simulated clock: an "advance one month" flow with its state in `sim.clock` | Active |
| [D-108](#d-108) | 2026-11-24 | 4.1 | Alerts recorded in `ops.alerts`; the channel that delivers them is chosen in F6 | Active |
| [D-109](#d-109) | 2026-11-24 | F5 | Scope of F5 and three pull requests: the API, the replayer, the published image | Active |
| [D-110](#d-110) | 2026-11-24 | 5.1 | The API loads the champions from the MLflow registry by their alias | Active |
| [D-111](#d-111) | 2026-11-24 | 5.1 | A new champion reaches the API by a notice from the flow, with polling as the safety net | Active |
| [D-112](#d-112) | 2026-11-24 | 5.1 | The API returns the risk, the expected return and whether it passes the buy threshold; the monthly cap stays with the investor | Active |
| [D-113](#d-113) | 2026-11-24 | 5.1 | `serving.predictions`: one row per prediction, columns for what is filtered, jsonb for what is audited | Active |
| [D-114](#d-114) | 2026-11-24 | 5.1 | A loan is stored once per pair of models (unique key in the database) | Active |
| [D-115](#d-115) | 2026-11-24 | 5.1 | Every request: a JSON log line and a row in `serving.requests`; rejected ones keep body and errors | Active |
| [D-116](#d-116) | 2026-11-24 | 5.1 | The API takes listings as the provider delivers them and cleans them with the code of the monthly load | Active |
| [D-117](#d-117) | 2026-11-24 | 5.1 | A batch answers each loan on its own; only a malformed batch is refused whole | Active |
| [D-118](#d-118) | 2026-11-24 | 5.1 | API keys, one list per permission, several valid at once for rotation | Active |
| [D-119](#d-119) | 2026-11-24 | 5.1 | FastAPI and uvicorn in the main dependencies, at the version Prefect allows | Active |
| [D-120](#d-120) | 2026-11-24 | 5.1 | The buy rule is registered in MLflow like a model, and chosen again when the champion pair changes | Active |
| [D-121](#d-121) | 2026-11-24 | 5.1 | A prediction is written before it is answered, in the same transaction | Active |
| [D-122](#d-122) | 2026-11-24 | 5.1 (changes T18.13) | Latency is measured under an open load of 20 requests a second; capacity is measured apart | Active |
| [D-123](#d-123) | 2026-11-25 | 4.2 (in F5) | The replayer is the simulated investor: a step of `advance`, after publishing a month and before the system's flow | Active |
| [D-124](#d-124) | 2026-11-25 | 4.2 (in F5) | The investor reports what it bought to the API (`POST /purchases`, `serving.purchases`) | Active |
| [D-125](#d-125) | 2026-11-25 | 4.2 (in F5) | The investor retries an API that does not answer, then stops the clock; a refused listing is not bought and is counted | Active |
| [D-126](#d-126) | 2026-11-25 | 4.2 (in F5) | Every answer carries a `prediction_id`; a purchase names only that id; exceptions to the rule are recorded, not refused | Active |
| [D-127](#d-127) | 2026-11-25 | 4.2 (in F5) | The investor starts the month after T0 | Active |
| [D-128](#d-128) | 2026-11-25 | 4.2 (in F5) | A purchase carries its amount, in notes of 25 dollars, up to the loan's amount | Active |
| [D-129](#d-129) | 2026-11-25 | 4.2 (in F5) | The client's own order number makes a repeated purchase harmless and allows repurchases | Active |

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

Date: 2026-11-23 · Step: 2.3 (audit decision 9.6) · Status: Superseded by D-069 (the window is now taken per term)

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

Date: 2026-11-23 · Step: 2.1 (changes the threshold of test B5, D-025/D-026) · Status: Superseded by D-078 (two images with their own budgets)

- **Context**: with polars in the package (D-046), the image grew from 211 MB to 456 MB and test B5 (at most 300 MB) failed. polars' compiled runtime alone takes 170 MB. The API needs polars to clean with the same code as the monthly load (D-045).
- **Decision**: the budget of B5 becomes **500 MB**.
- **Alternatives considered**: keep 300 MB and clean with pandas in the API (two implementations, against D-045); keep 300 MB with two images, one for loading with polars and one for the API without it (same two implementations, plus another image).
- **Why**: the size follows from a decision already taken; breaking the single-implementation rule to save 150 MB does not pay. 456 MB is a normal size for an ML service, and scikit-learn and model libraries will enter in F3 and F5.
- **Consequences**: B5 still catches anything that should not be in the image. The budget is reviewed when the model libraries enter.

<a id="d-053"></a>
### D-053 Validation rules written with pandera on polars

Date: 2026-11-23 · Step: 2.2 · Status: Active

- **Context**: step 2.2 needs rules that detect broken data before it reaches the model and stop the pipeline when a critical one fails.
- **Decision**: rules are written as **pandera** schemas on polars frames, validated in "lazy" mode so that every failure of a run is collected at once, not only the first. Each run writes its own report (JSON plus a readable summary). Rules that cross tables (every outcome has its listing) are SQL (D-045). Pydantic validates single API requests in F5, a different job.
- **Alternatives considered**: Great Expectations (best known, HTML reports, but heavy, complex and without polars support, so data would go through pandas against D-046); Pydantic row by row (slow for a month and blind to table rules such as volume or uniqueness); our own rules in polars and SQL (full control, but a tool of our own to test and maintain).
- **Why**: native on polars, light, rules are code reviewed in the pull request. Collecting every failure at once means one fix-and-rerun cycle instead of one per failure, and failures seen together point to a common cause. Checked on 2026-11-23 that pandera 0.36 works with polars 2.1.
- **Consequences**: the run report is ours to build. Great Expectations is not shown in this project.

<a id="d-054"></a>
### D-054 Two severity levels: a critical rule stops the run, a warning is reported and stored

Date: 2026-11-23 · Step: 2.2 · Status: Active

- **Context**: not every failed rule means broken data. Some values are impossible (a missing id, an unknown term), others are only unusual and can have a real-world cause (a month with 41% fewer loans after a peak, as in 2016-04 after 2016-03).
- **Decision**: every rule has one of two severities. A **critical** failure stops the run for that month: nothing reaches the clean layer and the load is logged as failed. A **warning** failure lets the run continue, appears in the run report and is stored in a table, so F6 monitoring can follow it over time. The severity of each rule is written next to the rule and approved with it.
- **Alternatives considered**: every rule critical (safe, but the pipeline would stop for normal market swings and people learn to ignore or bypass it); every rule a warning (never stops, so broken data could reach training unseen, against the rigor standard).
- **Why**: a critical rule says "this is impossible, do not go on"; a warning says "this is strange, a person should look". Mixing them up either blocks the pipeline for no reason or lets real errors through. Monthly volume in this data swings from -41% to +240% month over month, so volume rules compare against the same month of the previous year or a rolling median and are warnings; only an empty or absurd month is critical.
- **Consequences**: each rule needs a stated severity and reason. Warnings need a table and a place in the report. What happens to the rows of a month that fails a critical rule (stop the month or quarantine rows) is the next decision.

<a id="d-055"></a>
### D-055 A critical failure stops the whole month; no row quarantine

Date: 2026-11-23 · Step: 2.2 · Status: Active

- **Context**: D-054 says a critical failure stops the run. It does not say how much stops: the whole month, or only the rows that failed.
- **Decision**: if any row of a month fails a critical rule, nothing of that month reaches the clean layer, neither listings nor outcomes. The raw layer keeps the delivery as it arrived, so the failure can be inspected. The run report lists every failed row with its rule and value. After the fix, the month is run again; the idempotent load (D-049) makes the rerun safe. Values are never changed to make a row pass (D-051): an unseen value is either a provider error (ask for a new delivery) or a contract change (new cleaning rule with its test, in a reviewed pull request).
- **Alternatives considered**: quarantine of rows (good rows go to clean, bad rows to a quarantine table, the run goes on); a hybrid that quarantines below a threshold of failed rows and stops above it.
- **Why**: failed rows are rarely random, they share a cause (a new format in one segment), so removing them biases training without anyone noticing. Listings and outcomes go together: a quarantined outcome makes its loan look still running and loses its label, the censoring bias D-040 avoids. Stopping costs little with monthly retraining. Quarantine fits high-volume streaming systems where stopping costs money; here the equivalent is the F5 API, which rejects one bad request without stopping the service.
- **Consequences**: in step 2.3 the training set builder refuses to build at T if any month up to T is missing from clean, so a stopped month never becomes a silent gap. The report must be detailed enough to replace a quarantine table.

<a id="d-056"></a>
### D-056 Allowed values come from a dated contract: the 2013-12 base plus dated changes

Date: 2026-11-23 · Step: 2.2 · Status: Active

- **Context**: rules such as "`application_type` is `Individual`" need a list of allowed values and limits. Lending Club changed its product during the replay window: `home_ownership = ANY` from 2014-09, the first loans in North Dakota in 2015-07, joint applications in 2015-10, `DirectPay` disbursement in 2016-01, loans above 35,000 in 2016-03, the hardship program in the outcomes from 2017-06 (checked on the cleaned deliveries on 2026-11-23).
- **Decision**: the contract starts from what was known up to 2013-12, the last month loaded as history before the replay (D-041). Each later change is recorded as a dated contract change with its month of entry into force, its reason and its pull request, like a migration. A delivery is validated with the contract in force in its month. A value that arrives before its change enters into force fails as critical.
- **Alternatives considered**: (A) the 2014-01 list with a manual contract change each time, which stops again at every new run of the five-year replay; (B) the list from the whole file plus a warning when a value is seen for the first time, proposed first and rejected by Juan: it uses knowledge of the file's future to run operations, hiding the stops a real pipeline would have had; (C) the whole-file list without a warning.
- **Why**: the contract only knows the past, as in a real system, and product changes are handled the way a real team handles them, with a reviewed change. Once accepted, a change is part of the history, so later replays run unattended and still see, each month, the contract that would have been in force then.
- **Consequences**: a data test checks that the base contract alone stops the replay exactly at the months of the recorded changes, which shows that the stop works and that the list of changes is complete. Known simplification, documented: each change enters into force in the month the novelty first appears, as if the team reacted within the month.

### D-057 Every test is listed in a catalogue kept in step with the code by a test

Date: 2026-11-23 · Step: 2.2 (cross-cutting) · Status: Active

- **Context**: decisions and errors each have a log with an index and a card, but tests were only described in tables per step of technical.md, with `# Tx.y` comments in the code. There was no single list of every test, no record of what changed in an approved test and why, and nothing stopped the tables and the code from drifting apart. B1 to B5 and three data tests had no marker in the code.
- **Decision**: `docs/tests.md` lists every test with its ID, what it checks, its functions as `file::function`, its kind and where it runs, plus a change history. In the code, a comment `# <ID>` on the line before the first function of each test. Test B6 fails if a marker has no row, a row has no marker, a marker is in a file its row does not name, a row names a function that does not exist, or a test function in `tests/` is in no row (added on Juan's approval after two uncatalogued functions were found, now T3.14 and T3.15).
- **Alternatives considered**: keep the tables in technical.md only (no history, drifts silently); generate the catalogue from docstrings (the code becomes the only source, but the approval record and the history need a place of their own); pytest markers such as `@pytest.mark.test_id("T3.4")` (machine-readable, but noisier than a comment and still needs the catalogue).
- **Why**: Juan approves every test, so the catalogue is the record of what he approved; a test that checks it keeps the record true without relying on memory.
- **Consequences**: adding or changing a test means a row and a history line in the same pull request, or B6 fails in CI. The tables of technical.md stay as the summary of each step and link to the catalogue.

### D-058 A training set version is an immutable snapshot plus a manifest of where it came from

Date: 2026-11-23 · Step: 2.3 · Status: Active

- **Context**: a model must be reproducible months later, so the exact rows it was trained on must be known. The training set at date T is built from `clean` (matured cohorts, D-040; last 6 months as validation, D-042), but `clean` changes: a corrected delivery replaces its month (D-049), so the same query at the same T can return different rows later.
- **Decision**: a SQL query builds the training set at T; the result is saved once as an immutable Parquet file with a manifest: T, the git commit of the code, the `load_id` of every month used, the number of rows and the hash of the content. Training reads the saved copy, never the live query. Rebuilding with the same manifest must give the same hash; a different hash means a month changed since.
- **Alternatives considered**: (A) the version is the cutoff date T and the set is rebuilt on demand (no storage, but not reproducible after a correction); (B) a saved copy identified by its hash only (reproducible, but nothing records which loads it came from).
- **Why**: the copy makes training reproducible whatever happens to `clean` later; the manifest explains it and lets a check find every set, and so every model, built on a load that has since been replaced. This is what tools such as DVC, lakeFS or Delta time travel give: a fixed copy plus a record of its origin.
- **Consequences**: storage grows with every training; where copies and manifests live is the next decision. A correction never changes an old set: the old set stays as the record of what the model saw, and the set is flagged as built on a replaced load.

### D-059 Snapshots in object storage by content hash; manifests in Postgres

Date: 2026-11-23 · Step: 2.3 · Status: Active

- **Context**: every training produces a new snapshot (D-058); the one at 2018-12 was estimated at over a million rows and a few hundred MB (measured later: 522,904 rows, 67 MB, technical.md step 2.3). Snapshots are produced by the pipeline on its own, not by a person working in git.
- **Decision**: each snapshot is a Parquet file at `training_sets/<hash>.parquet` in object storage: a local folder for now, an S3 bucket with versioning in AWS. Its manifest is a row of `ops.training_sets` (T, git commit, rows, hash, path) with the `load_id` of every month used as foreign keys to `ops.ingest_log`. Finding the sets built on a load that was later replaced is a SQL query. From F3, MLflow stores the hash with each model.
- **Alternatives considered**: (A) DVC, the best known tool, which keeps a `.dvc` pointer in git and the file in remote storage: it fits a person versioning data with the code, but here the pipeline would have to commit to git at every training; (C) everything in Postgres, one table per version: simple and all SQL, but the database grows with large copies and training reads from it.
- **Why**: each piece goes where it is handled best: large immutable files to object storage, metadata that must be queried to the database. It maps directly to S3 in AWS.
- **Consequences**: the path is the content hash, so a path can never point to different content, the same content is stored once and a file is never overwritten. A storage layer with a local and an S3 implementation; the local folder stays out of git.

### D-060 A snapshot is two files: what training may see, and what only evaluation may see

Date: 2026-11-23 · Step: 2.3 · Status: Active

- **Context**: a snapshot serves two purposes. Training needs the columns visible at listing (D-014) and the label (D-040). Evaluation in money needs payments, recoveries and the funded amount: realised return (D-007) and LGD (D-017). Those are future information; if the model saw them, it would be pure leakage.
- **Decision**: one version, one manifest, two files joined by `id`. `features.parquet` holds every column of `clean.listings`, the label and the split (train or validation). `evaluation.parquet` holds the outcome columns. Training receives only the path of the first. A test checks that the first holds no outcome column.
- **Alternatives considered**: (A) features and label only: safest, but evaluation in money goes back to `clean` and is no longer reproducible from the snapshot; (B) everything in one file with a prefix on the evaluation columns: reproducible, but one wrong `select` puts future payments into the model.
- **Why**: the structure prevents the leak instead of relying on discipline, and evaluation stays reproducible. `features.parquet` keeps every listing column, not only the model's: which columns the model uses and how they are prepared is step 2.4, so the snapshot does not depend on it.
- **Consequences**: the version path of D-059 becomes a folder, `training_sets/<hash>/` with both files; the hash covers both. The label is allowed in the training file although it comes from the future because it is the target, never an input, and exists only for matured cohorts.

### D-061 Two hashes: the content hash names a version, the file checksum guards the stored file

Date: 2026-11-23 · Step: 2.3 · Status: Active

- **Context**: the hash names a version (D-059) and checks that a rebuild gives the same data (D-058). That check must fire when the data changes, and only then. A Parquet file stores the version of the library that wrote it, its compression and its row groups, so the same data can give different bytes.
- **Decision**: the **content hash** is SHA-256 over a canonical text form of the data: rows sorted by `id`, columns in a fixed order with their types, each value written in one fixed way. It is the identity and the path of the version. The **file checksum** (SHA-256 of the bytes of each stored file) goes in the manifest and is verified every time a file is read.
- **Alternatives considered**: (A) the hash of the file bytes only: simple, but updating polars changes the bytes and the rebuild check raises false alarms, which teaches people to ignore it; (B) the content hash only: no way to tell that a stored file was corrupted or altered. polars `hash_rows` was rejected: its documentation warns that its result may change between versions.
- **Why**: "are these the same data?" and "is this the file I stored?" are two different questions, each with its own hash.
- **Consequences**: if a version is rebuilt and its path already exists, nothing is written: the content hash proves the data are the same, and the stored file is verified against its checksum; a failed checksum stops with an error instead of overwriting.

### D-062 Two layers of preparation: fixed transformations in the package, learned ones inside the model

Date: 2026-11-23 · Step: 2.4 · Status: Active

- **Context**: features are computed at prediction time too, so they are written once, in Python (D-045). Preparation is of two kinds. Fixed transformations learn nothing from the data (length of credit history from `issue_d` and `earliest_cr_line`, FICO midpoint, logarithm of income) and give the same result with any training set. Learned transformations are fitted on data (median to fill a gap, known categories of `purpose`, mean and spread to scale); fitted on validation rows, they leak.
- **Decision**: fixed transformations live in `features.py`: pure polars functions with no state, the same in training, in the API and in monitoring, versioned with the package. Learned transformations live inside the model pipeline (F3), fitted on the training split only and saved with the model.
- **Alternatives considered**: (A) everything in one scikit-learn pipeline saved with the model: a single artifact, but the fixed transformations are tied to it and harder to test and to reuse in monitoring; (C) a feature store such as Feast: built to share features across many teams and models, far too much for one model.
- **Why**: each kind lives where it makes sense. Fixed transformations are tested as plain functions and monitoring can watch them; learned ones cannot see validation because they exist only inside the fitted model.
- **Consequences**: a learned value (such as the median of `dti`) never appears in `features.py`: it depends on the training set, so it must be fitted on train only and travel with the model; in `features.py` it would be either a constant from nowhere or a value computed on whatever arrives (one row in the API).

### D-063 v1 features: the columns filled since 2007 plus two required transformations; engineered features are F3 experiments

Date: 2026-11-23 · Step: 2.4 · Status: Active

- **Context**: building features (ratios, logarithms, combinations) is a modelling experiment: each new feature can help, do nothing or add noise, and only a measurement against the metric noise tells which (the challenger rule of D-015).
- **Decision**: `features.py` does only what a model needs to read the data, plus the selection already decided. It computes the **length of credit history** in months at listing (`issue_d` minus `earliest_cr_line`) and the **FICO midpoint** (`fico_range_high` is `fico_range_low` + 4, or + 5 in 441 loans). It keeps the columns proven visible at listing (D-014) and filled since 2007 (D-016), without free text (D-015), state or zip code (D-018). `installment` stays out until F3 decides whether to recompute it (the funded-amount leak, data_audit section 3). Every other engineered feature enters as an F3 experiment.
- **Alternatives considered**: (B) a rich set from the start (loan to income, instalment to income, logarithm of income, revolving balance to limit, `sub_grade` as a number from 1 to 35): more signal at once, but features chosen without evidence, and the first model is no longer a clean reference for what comes later.
- **Why**: each engineered feature must earn its place with evidence; the first model is a clean starting point.
- **Consequences**: 30 inputs. 22 numeric: `loan_amnt`, `term`, `int_rate`, `emp_length`, `annual_inc`, `dti`, `delinq_2yrs`, `inq_last_6mths`, `mths_since_last_delinq`, `mths_since_last_record`, `open_acc`, `pub_rec`, `revol_bal`, `revol_util`, `total_acc`, `collections_12_mths_ex_med`, `acc_now_delinq`, `chargeoff_within_12_mths`, `delinq_amnt`, `tax_liens`, the FICO midpoint and the credit history. 8 categorical: `grade`, `sub_grade`, `home_ownership`, `verification_status`, `purpose`, `initial_list_status`, `application_type`, `disbursement_method`. `pub_rec_bankruptcies` stays out by D-016: it is missing in 583 of 603 loans of 2007 and 779 of 2008, and filled only from 2009. Missing values stay missing: filling them is learned (D-062). The FICO midpoint is kept instead of `fico_range_low` alone because it is the score the range stands for, also for the 441 loans with a 5-point range.

### D-064 Coverage: 85% of branches over unit and integration tests, 90% of the lines each pull request changes

Date: 2026-11-23 · Step: F2 (cross-cutting, closes D-031) · Status: Active

- **Context**: D-031 left the minimum for F2, on real code. Branch coverage measured on 2026-11-23: unit tests alone 58%, because loading (`ingest.py`) and versioning (`snapshot.py`) are SQL run by Postgres and only the integration tests exercise them; unit and integration tests together 89%, with only the two command-line entry points at 0%.
- **Decision**: CI (integration job, `make test-integration`) measures unit and integration tests together and fails below **85%** of branches. `make diff-cover` fails when less than **90%** of the lines a pull request adds or changes are covered, compared with `origin/main`. The `if __name__ == "__main__":` lines are left out of the count. The unit job still shows its own number, without a minimum.
- **Alternatives considered**: (A) a minimum on unit tests alone, around 55%: almost meaningless for the SQL code, or a push to mock Postgres, which is what SQL must not be tested against; (B) 85% over unit and integration only: simple, but a pull request could add untested code while the total stays above 85%.
- **Why**: 85% protects what exists; 90% on new lines makes every change bring its tests, which is what D-031 meant by "no PR may lower coverage", without freezing an arbitrary number. 100% was not chosen: it pushes tests that execute lines without checking anything (Goodhart's law) and costs most on defensive branches that are hard to reach. Juan approving every test stays the main defence.
- **Consequences**: new dev dependency `diff-cover`; the CI checkout of the integration job fetches the full history to compare with `main`.

### D-065 The audit notebook runs in CI every week and on pull requests that touch it, and must reproduce its outputs

Date: 2026-11-23 · Step: F2 (cross-cutting, closes the open point of D-021) · Status: Active

- **Context**: Juan asked in F1 to run notebooks top to bottom in CI, once the data download existed. There is one notebook, the data audit. It downloads the 1.6 GB file from Kaggle itself, checks its hash, runs in about 2 minutes, and its outputs in `reports/data_audit` are deterministic (E-010).
- **Decision**: a `Notebooks` workflow runs `make notebooks` every Monday, by hand, and on pull requests that touch `notebooks/`, `reports/data_audit/`, `uv.lock` or the workflow. It fails if the notebook raises an error or if any file of `reports/data_audit` differs from the committed one. The Kaggle token is a repository secret, `KAGGLE_API_TOKEN`. The notebook file itself is not compared: execution timestamps and kernel metadata change on every run.
- **Alternatives considered**: (A) on every pull request: the Kaggle token and 1.6 GB on every run, and several minutes more for a notebook that almost never changes; (C) only locally with `make test-data`: free, but nobody watches it.
- **Why**: the notebook cannot break in silence and normal pull requests stay fast. Running without an error is not enough: a library update or a change in the data could change a number without any error, so the outputs are compared like a regression test.
- **Consequences**: Juan adds the `KAGGLE_API_TOKEN` secret to the repository. Checked on 2026-11-23: the notebook ran in 1 min 53 s and every file of `reports/data_audit` came out byte-identical. The first run on GitHub drew the figure differently from the cloud machine, and Juan decided to leave the PNG figures out of the comparison; the tables they draw are still compared (E-024). Added on 2026-11-23 (E-026): workflows started by Dependabot only see Dependabot secrets, so `KAGGLE_API_TOKEN` must exist twice, as an Actions secret and as a Dependabot secret, both under Settings > Secrets and variables.

<a id="d-066"></a>
### D-066 uv, the uv_build backend and the uv Docker image move together, to 0.13.9

Date: 2026-11-23 · Step: F3 (cross-cutting, first task of F3) · Status: Active

- **Context**: uv appears in three places: the `UV_VERSION` of every workflow (`ci.yml`, `security.yml`, `notebooks.yml`), the `astral/uv` image of the `Dockerfile`, and the build backend `uv_build` in `pyproject.toml`. Dependabot PR #3 proposed `uv_build>=0.13.9,<0.14` alone, which would have left the backend two minor versions ahead of the uv that builds it. All three were at 0.11.32 (`uv_build>=0.9,<0.12`).
- **Decision**: one pull request moves the three together: `UV_VERSION: "0.13.9"` in every workflow, `astral/uv:0.13.9` pinned by digest (`sha256:d3b601f0...`) in the `Dockerfile`, and `uv_build>=0.13.9,<0.14` in `pyproject.toml`. Juan closed Dependabot PR #3.
- **Alternatives considered**: (A) merge Dependabot PR #3 as it was: backend and frontend out of step, CI and the image would still build with 0.11; (B) stay on 0.11 until something breaks: the gap only grows and the jump gets harder.
- **Why**: uv and `uv_build` are released together and tested together. One version everywhere means the machine, CI and the image build the package in exactly the same way. The upper bound `<0.14` keeps a future minor release from entering without a pull request, since uv is still before 1.0 and a minor release can change behaviour.
- **Consequences**: `uv.lock` did not change (`uv lock --check` passes with 0.13.9). Checked here with uv 0.13.9: `make lint`, `make test` (139 tests), `uv build`, `make build`, `make test-image` and `make test-integration` (coverage 90%) all pass; image size unchanged (466 MB). Future uv updates follow the same rule: the three places in one pull request.

<a id="d-067"></a>
### D-067 F3 fixes a training procedure, not a model, using only data available at T0

Date: 2026-11-23 · Step: 3.1 · Status: Active

- **Context**: the whole file, up to 2018, is on disk. F3 designs what is trained at T0 = 2014-01 (D-041): 7,733 training loans and 4,324 validation loans (D-042, measured in step 2.3). The same design is run again at every retraining (F4, F6), on up to about 500,000 loans. Settings that suit 7,745 loans (shallow trees, strong regularisation) may not suit 500,000.
- **Decision**: every design choice of F3 is made with the T0 snapshot only. What F3 fixes is a **procedure**: the candidate models, how their hyperparameters are searched, how the winner is chosen and calibrated. The search runs again at every retraining, on the training and validation sets of that date. Alternative models enter later as challengers, under the promotion rules of step 3.3.
- **Alternatives considered**: (A) fix concrete values at T0 (for example depth 2 and 150 trees) and only refit them later: honest, but the values never adapt to more data; (B) design with snapshots of later dates (backtesting): the validation of a 2018 snapshot holds loans of 2015, inside the replay used as test (D-041), so the design would carry information from the future and the final business metric would be optimistic (data snooping).
- **Why**: in a real system nobody at T0 knows the future, and nobody freezes hyperparameters forever: they automate how they are chosen. Each choice uses only what was known at its date, as already required by D-056.
- **Consequences**: a retraining takes longer, because it includes the search; F3 must fix the search budget and the candidate list. Nothing in F3 reads a snapshot later than 2014-01.

<a id="d-068"></a>
### D-068 PD candidates: logistic regression and one gradient boosting model; within the noise, the simpler wins

Date: 2026-11-23 · Step: 3.2 · Status: Active

- **Context**: D-067 makes the candidate list part of the training procedure, so every candidate is searched again at every retraining. In the research phase, logistic regression (AUC 0.685) tied with three other models within the sampling error (about 0.003). At T0 the validation set has 429 defaults, so the error of the AUC is about ten times larger (roughly 0.015, to be measured by bootstrap in step 3.2).
- **Decision**: two candidates for the PD: a **regularised logistic regression** on the 30 v1 features (with learned imputation, encoding and scaling inside its pipeline, D-062) and **one gradient boosting model** (library decided separately). If their difference on validation is within the metric noise, the logistic regression wins.
- **Alternatives considered**: (A) logistic regression only: simplest, but it can never use interactions even when data grow; (C) six models as in the research phase: the search at every retraining costs about six times more, for models that did not win there.
- **Why**: the two archetypes of tabular modelling. The logistic regression is stable with little data, transparent and the regulatory standard in scoring; gradient boosting finds interactions and non-linear effects and handles missing values natively, which pays off with more data. Under D-067 the data of each date decide between them. The tie rule prefers what is easier to explain, check and maintain when the data cannot tell them apart.
- **Consequences**: two preparation pipelines to maintain and test. The exact form of "within the noise" is fixed with the promotion rules (step 3.3).

<a id="d-069"></a>
### D-069 Validation split per term: the last 6 matured listing months of each term

Date: 2026-11-23 · Step: 3.1 (supersedes D-042) · Status: Active (implemented in the first F3 pull request, data)

- **Context**: D-042 takes the last 6 listing months of all matured loans as validation. A 60-month loan matures 24 months later than a 36-month one (D-040), so the last 6 matured months are always 36-month loans: the validation set never holds a 60-month loan, at any cutoff. Selection, calibration and the tests by segment would never see them, although 60-month loans were 25.5% of the loans listed in 2013 (34,000 of 134,800; information available at T0).
- **Decision**: the window is taken **per term**. At cutoff T, validation holds the 36-month loans listed from T-46 to T-41 and the 60-month loans listed from T-70 to T-65; earlier matured loans of each term are training. Everything else of D-042 stays: out of time, metric noise by bootstrap on validation, nothing that learns or chooses may touch the test (the forward replay).
- **Alternatives considered**: (A) keep D-042: no 60-month loan in validation, ever; (C) one model per term: each one specialises, but it splits data that are already scarce and doubles what must be maintained and monitored.
- **Why**: a small, local change that puts both terms into validation in their natural proportion, and keeps each term out of time on its own.
- **Consequences**: the 60-month validation is two years older than the 36-month one. Across terms, the training set can hold 36-month loans listed after some 60-month validation loans (at 2018-12: 36-month training up to 2015-01, 60-month validation 2013-02 to 2013-07), so the period conditions the model learned from those later loans can make the 60-month validation slightly optimistic; accepted and documented. `sql/training_ids.sql`, its tests (T5.4 and the polars cross-check T5.12) and the measurements of step 2.3 change; the test changes need Juan's approval first. What to do while a term has no matured loans (60-month loans at T0) is a separate decision.

<a id="d-070"></a>
### D-070 Coverage rule: a term is scored only with at least 200 defaults in its training and 200 in its validation

Date: 2026-11-23 · Step: 3.1 · Status: Active

- **Context**: 60-month loans started in 2010-05 and mature 65 months later (D-040), so at T0 the model has not seen a single one, and `term` is constant in its training set. Yet they were 25.5% of the loans listed in 2013 (D-069), so about one in four loans of the replay would be scored by a model that never saw their kind. Counting dates only (no outcomes), 60-month loans get their own training and validation loans around 2016.
- **Decision**: each model records the terms it **covers**: a term is covered when the model's training set holds at least **200 defaults** of that term and its validation set (D-069) at least **200**. A loan of a term the champion does not cover gets no PD: it is marked out of coverage and is not bought. A term becomes covered at the first retraining that meets the rule. The minimum may be revised once the metric noise is measured (step 3.2).
- **Alternatives considered**: (A) score every loan anyway: a 36-month risk for a 60-month loan, almost surely too low, and the error flows into expected loss and the buy decision; (C) adjust 60-month risk with partial outcomes observed by T0: scores everything from the start, but uses incomplete outcomes, the bias D-040 ruled out, and is hard to validate.
- **Why**: an investor buys only what their model can assess. With fewer than about 200 defaults the error of the AUC and of the calibration of a term is too large to rely on (at T0, with 429 validation defaults in all, the AUC error is about 0.015).
- **Consequences**: until 60-month loans are covered, about a quarter of the listed loans is not bought. The API, the stored predictions and the buy rule must handle "out of coverage". The business metric (D-007) compares our portfolio and the baseline portfolio on the same eligible loans with the same budget, and the share of loans out of coverage is reported apart. The covered terms are stored with each model.

<a id="d-071"></a>
### D-071 `installment` never enters; a recomputed instalment and its ratio to income are F3 experiments

Date: 2026-11-23 · Step: 3.2 (closes the open point of D-063) · Status: Active

- **Context**: `installment` looks like listing data, but Lending Club computes it on the funded amount, not on the requested one (data audit, section 3): in the 2,062 resolved loans that were not fully funded (0.15%) it reveals something known only after listing. It is also an exact function of `loan_amnt`, `int_rate` and `term` (the amortisation formula), so a recomputed value adds no new information, only a combination of the three.
- **Decision**: the `installment` column never enters a model. The instalment recomputed from `loan_amnt`, `int_rate` and `term`, and its ratio to monthly income (`instalment / (annual_inc / 12)`), are tested as engineered-feature experiments in F3, and enter only if they improve the metric by more than its noise (D-063).
- **Alternatives considered**: (A) drop it for good, including any recomputed version: simplest, but it gives up the payment burden, a classic of credit scoring; (B) recompute it and add it to the base features now: no leak, but it is feature engineering without evidence, which D-063 left to experiments.
- **Why**: the original column leaks; the recomputed one is engineering, and must earn its place like any other engineered feature. A logistic regression adds the effects of its inputs, so it cannot build the amortisation formula or a ratio to income by itself; the experiment tells whether giving it that combination helps.
- **Consequences**: the recomputation is a fixed transformation, so if it enters it lives in `features.py` (D-062), with tests against the amortisation formula. The experiment runs on the T0 snapshot only (D-067).

<a id="d-072"></a>
### D-072 The gradient boosting candidate is LightGBM

Date: 2026-11-23 · Step: 3.2 · Status: Active

- **Context**: D-068 adds one gradient boosting candidate. The libraries differ in speed, handling of categories and missing values, SHAP support and weight; the image is at 466 MB of a 500 MB budget (D-052). Download sizes of the Linux wheels, measured on 2026-11-23: LightGBM 4.7.0 3.4 MB; XGBoost 3.4.1 55 MB plus NVIDIA NCCL on Linux; CatBoost 1.2.10 93 MB; scikit-learn's HistGradientBoosting nothing extra.
- **Decision**: **LightGBM**.
- **Alternatives considered**: XGBoost (as complete and mature, but brings GPU libraries we do not use, hundreds of MB); CatBoost (best with categories, used for the LGD in the research phase, but heavy and slower to train); HistGradientBoosting (no new dependency, but fewer options and more limited exact SHAP support).
- **Why**: the standard for tabular credit scoring and the lightest option. It handles missing values natively (it learns which branch they go to, so "never delinquent" in `mths_since_last_delinq` is not turned into an invented value), supports monotone constraints, and computes exact SHAP contributions itself (step 3.5).
- **Consequences**: the image needs the system library `libgomp1`. scikit-learn, scipy and numpy (needed by the logistic regression) will push the image past 500 MB: a separate decision.

<a id="d-073"></a>
### D-073 Hyperparameters are tuned on an inner time split of the training set; validation stays clean

Date: 2026-11-23 · Step: 3.2 (closes part of the open point of D-042) · Status: Active

- **Context**: tuning tries many settings and keeps the one that scores best on some set. The winner always looks better on that set than it is, because part of its lead is luck (the winner's curse), and the more settings tried and the smaller the set, the larger the bias. If the same set is then used to compare with the baseline, measure the metric noise and calibrate, all of these come out optimistic.
- **Decision**: inside the training set, the last 6 listing months of each term (as in D-069) form an **inner validation set**; the earlier months form the inner training set. Each candidate's hyperparameters are tuned on this inner split; the candidate is then refitted on the whole training set with the chosen values. The validation set (D-069) is used only after tuning: comparison of candidates, comparison with the baseline and the champion, metric noise, calibration.
- **Alternatives considered**: (A) tune on the validation set directly: simple, but it is then spent and every later comparison is optimistic; (C) time-series cross-validation inside training (several expanding windows): the most robust, but several times dearer at every retraining, and at T0 its first windows (2007 and 2008) hold very few defaults.
- **Why**: the same time logic as the outer split, at little cost, and the validation set stays honest for the decisions that matter most.
- **Consequences**: at T0 tuning works with little data: about 4,700 inner training and 3,000 inner validation loans (estimated from listing counts); it grows by itself at later retrainings. A term with no loans in the inner window is tuned on the other term only. Whether calibration needs its own part of validation, and whether to refit on training plus validation, are still open.

<a id="d-074"></a>
### D-074 Search: Optuna TPE with 50 seeded trials for LightGBM, a grid over `C` for the logistic regression

Date: 2026-11-23 · Step: 3.2 · Status: Active

- **Context**: the search runs at every retraining (D-067) on the inner split (D-073). LightGBM has about six hyperparameters that matter; the logistic regression has one, the strength of its regularisation `C`.
- **Decision**: **LightGBM**: Bayesian search with Optuna's TPE sampler, **50 trials**, fixed seed, early stopping on the inner validation set (so the number of trees is chosen by the data). **Logistic regression**: a grid of about 20 values of `C` on a log scale. The budget is a number of trials, never a time limit.
- **Alternatives considered**: (A) grid search for both: exhaustive, but the grid explodes with six hyperparameters; (B) random search with a fixed number of trials: simple and good, but it does not learn from earlier trials.
- **Why**: TPE spends its trials where results are good and can stop bad trials early; Optuna records trials in a way MLflow can log (step 3.2). With a single hyperparameter, a grid is already the best search. A time budget depends on the machine's speed and load, so the same code, data and seed could give a different model; a fixed number of trials keeps the run reproducible (playbook 3.2: the same seed gives the same metrics).
- **Consequences**: Optuna becomes a training dependency only, not needed to serve predictions. The 50 trials and the ranges searched are fixed in code and logged with every run; changing them is a new decision.

<a id="d-075"></a>
### D-075 "Better by more than the noise": the 95% paired bootstrap interval of the difference lies above zero

Date: 2026-11-23 · Step: 3.2 (defines the noise rule used by D-042 and D-068) · Status: Active

- **Context**: "better by more than the metric noise" decides three things: logistic regression against LightGBM (D-068), the chosen model against the baseline, and later a challenger against the champion. D-042 fixed that noise is measured by bootstrap on the validation set, but not how two models are compared.
- **Decision**: **paired bootstrap of the difference**. The validation set is resampled with replacement 1,000 times, with a fixed seed, stratified by label (each resample keeps the number of defaults and non-defaults). In each resample both models are scored on the same loans and the difference of the metric (new minus current) is computed. The new model wins only if the 95% interval of the 1,000 differences lies entirely above zero (below zero for a metric where lower is better, such as the Brier score). Otherwise there is no clear winner and the simpler or the current model stays.
- **Alternatives considered**: (A) a separate interval for each model, with a win only if they do not overlap: intuitive, but it counts the noise the two models share twice and misses real gains; (C) DeLong's test: a closed formula, but for AUC only.
- **Why**: two models scored on the same loans move up and down together from one resample to the next; that shared movement is most of the noise of each AUC and cancels in the difference. A simulation with the size of the T0 validation set (4,324 loans, 429 defaults) and two models sharing most of their signal gave AUC 0.655 (95% interval 0.628 to 0.684) and 0.681 (0.655 to 0.707): the intervals overlap, but the paired difference, 0.026, had an interval from 0.012 to 0.040 (spread 0.007 against 0.014 for each model). The method works for any metric.
- **Consequences**: one shared function computes the paired comparison for every use (candidates, baseline, champion and challenger). Its intervals and the 1,000 differences are logged with each run.

<a id="d-076"></a>
### D-076 The PD is calibrated with Platt scaling fitted on the validation set

Date: 2026-11-23 · Step: 3.2 (closes part of the open point of D-042) · Status: Active

- **Context**: AUC measures only ranking and does not change under any transformation that keeps the order, so a model can rank well with the wrong level. The PD multiplies into expected loss (D-002), so its level matters. At T0 the training set defaults at 13.2% (1,019 of 7,733, listed 2007 to 2010-02) and the more recent validation set at 9.9% (429 of 4,324): a model trained as is keeps the older level. Regularisation also pulls predictions towards the mean.
- **Decision**: the chosen model's output is calibrated with **Platt scaling** (a logistic regression with two parameters on the model's log-odds) fitted on the validation set. The calibration quality reported for a model (Brier score and calibration by segment, D-006) is measured by 5-fold cross-fitting inside validation: the calibrator is fitted on four parts and measured on the fifth, five times.
- **Alternatives considered**: (A) no calibration: the PD keeps the level of the training period and expected loss is inflated; (C) split validation into a selection half and a calibration half: clean, but more noise in both with 429 defaults. Isotonic regression instead of Platt: no fixed shape, but it overfits with a few hundred defaults.
- **Why**: it moves the level to the most recent known period with only two parameters, stable with 429 defaults. Platt keeps the order, so the AUC and every paired AUC comparison of D-075 are not affected by it.
- **Consequences**: the deployed model is the pair model plus calibrator. Isotonic calibration may enter later as a challenger once data are larger. Whether to refit the model on training plus validation is a separate decision.

<a id="d-077"></a>
### D-077 No refit on training plus validation: the deployed model is exactly the one measured

Date: 2026-11-23 · Step: 3.2 (closes the open point of D-042) · Status: Active

- **Context**: refitting the chosen model on training plus validation is common practice: at T0 validation adds 4,324 loans to 7,733, the most recent ones. But here validation compares candidates and the baseline (D-075) and fits the calibrator (D-076).
- **Decision**: no refit. The deployed model is the one trained on the training set, with the calibrator fitted on validation: exactly the pair that was measured.
- **Alternatives considered**: (B) refit and reuse the calibrator: more data, but the calibrator was fitted on the outputs of another model, and the deployed model was never measured; (C) refit and calibrate on out-of-sample predictions from time windows: uses everything, but far more complex, and the deployed model is still not measured directly.
- **Why**: after a refit no clean data would remain to check that the final model beats the baseline: only the forward test, years later, after it had already been deciding purchases. In a regulated field such as credit, the artefact deployed is the artefact validated. The recent months are not lost: the calibrator moves the level to them, and the next retraining puts them in training.
- **Consequences**: the ranking at each date is learned without the latest 6 matured months of each term. Option C may be tried later as a challenger.

<a id="d-078"></a>
### D-078 Two images from one Dockerfile: `serve` (budget 800 MB) and `train` (budget 1.5 GB)

Date: 2026-11-23 · Step: 3.2 (supersedes D-052, changes test B5) · Status: Active (budgets to be confirmed by measuring the real images)

- **Context**: the image is at 466 MB of a 500 MB budget (D-052). Installed size added by the F3 libraries, measured on 2026-11-23 in clean environments (approximate, they share some dependencies): scikit-learn and LightGBM 209 MB; plus mlflow-skinny 280 MB; scikit-learn, LightGBM, Optuna and full MLflow 643 MB; SHAP 252 MB. Serving needs only to load a model and predict; training also needs the search, tracking and reports.
- **Decision**: two build targets of the same Dockerfile, from the same `uv.lock`. **`serve`**: the package with scikit-learn, LightGBM and mlflow-skinny, budget **800 MB**. **`train`**: everything in `serve` plus Optuna, full MLflow and SHAP, budget **1.5 GB**. The training-only libraries go into a `train` dependency group.
- **Alternatives considered**: (A) one image with everything, budget about 1.5 GB: simple, but the API carries hundreds of MB it never uses; (C) no MLflow in serving, with a home-made model format: the smallest image, but custom code to save and load models, which MLflow already solves, and a source of errors.
- **Why**: each image carries only what it uses. The serving image matters most: it is pulled at every deployment and every scale-out (start-up time and transfer cost), and it runs all the time exposed to the network, so every extra library is attack surface and more findings for Trivy. The training image runs now and then, as a batch job, exposed to nobody.
- **Consequences**: CI builds, tests and scans two images. Test B5 checks each image against its own budget (the test change needs Juan's approval). Per-prediction SHAP values do not need the `shap` library in the API: LightGBM computes them itself and for the logistic regression they are coefficient times value. The budgets are set from the measured images in the F3 pull request.

<a id="d-079"></a>
### D-079 Tracking: an MLflow server in docker compose, metadata in its own Postgres database, artefacts in object storage

Date: 2026-11-23 · Step: 3.2 · Status: Active

- **Context**: every training produces what must be found months later: the hyperparameters tried, metrics and their bootstrap intervals (D-075), the commit, the snapshot hash (D-059), library versions and the model itself. The model registry is also what will name the champion (step 3.4). MLflow stores metadata (small and queryable) and artefacts (models, figures, reports).
- **Decision**: an **MLflow tracking server** as a docker compose service. Metadata go to a separate database, `mlflow`, in the existing Postgres; artefacts go to object storage: a local folder (volume) now, an S3 bucket in AWS. Every run must carry a fixed list of required fields (commit, snapshot hash, seed, library versions, metrics with their intervals), and a test checks that no run is logged without them (playbook 3.2).
- **Alternatives considered**: (A) MLflow without a server, in a local `mlruns/` folder: no infrastructure, but no reliable concurrent access, the model registry needs a database, and it looks nothing like production; (C) a managed service (Weights & Biases, Databricks): polished, nothing to run, but an external account, cost, data leaving the system, and the chosen cloud is AWS.
- **Why**: the same split as D-059: large immutable files to object storage, queryable metadata to the database. Moving to AWS changes only the artefact address. Large binaries in Postgres would bloat its backups and pay for a database without using what makes it useful.
- **Consequences**: one more service in compose and in the integration tests. The MLflow server image is pinned by version and digest like the others (D-030), and Dependabot watches it.

<a id="d-080"></a>
### D-080 Monotone constraints on nine features with an undisputed direction; sign test for the logistic regression

Date: 2026-11-23 · Step: 3.3 · Status: Active

- **Context**: some features have a clear direction of effect on risk. A flexible model such as LightGBM can learn stretches the wrong way through noise, above all with 7,733 training loans, which would give explanations such as "refused for having a higher FICO". A monotone constraint, applied with every other feature held equal, lets the prediction move in one direction only along that feature. LightGBM supports it; a logistic regression cannot enforce it, but the sign of its coefficients can be checked.
- **Decision**: LightGBM is constrained on nine features. **Risk does not fall when these rise**: `int_rate`, `dti`, `revol_util`, `inq_last_6mths`, `delinq_2yrs`, `pub_rec`. **Risk does not rise when these rise**: the FICO midpoint, `annual_inc`, the length of credit history. For the logistic regression, a model test fails if any of these nine coefficients has the opposite sign. `grade` and `sub_grade` are categorical in v1 and are not constrained.
- **Alternatives considered**: (A) no constraints, with a directional test that rejects the model if it fails: most flexible, but with little data it fails through noise and there is no fix short of changing the model; (C) constraints on every numeric feature: most interpretable, but it forces a made-up direction where none is clear (`total_acc`, `revol_bal`).
- **Why**: consistent explanations, more robustness to changes in the data, and standard practice in regulated scoring, limited to where the direction is beyond dispute. The constraint holds everything else equal, so a borrower who earns more but borrows much more is still riskier, through `dti`. Before relaxing a constraint, an apparent reversal is checked against the number of loans in that range (bootstrap interval) and against `verification_status`, since high unverified incomes may be inflated.
- **Consequences**: a small loss of AUC is possible if a real effect is not monotone; a constraint is removed only by a new decision with that evidence. The list is fixed in code and logged with every run.

<a id="d-081"></a>
### D-081 Key segments: grade, covered term and listing quarter; a new model fails if it is clearly worse in any of them

Date: 2026-11-23 · Step: 3.3 · Status: Active

- **Context**: a model can raise the global AUC while getting worse in one group, for example ranking grades A to C better (most loans) and grades E to G worse. Testing many segments has its own problem: with 20 segments and two equally good models, the chance that at least one fails by luck is about 40% (1 - 0.975^20).
- **Decision**: blocking segments are `grade` (F and G merged), `term` (covered terms only, D-070) and the listing quarter inside validation; a segment with fewer than 50 defaults is merged with its neighbour. In each segment two things are compared with the paired bootstrap of D-075: the AUC inside the segment, and the calibration error (absolute difference between the mean predicted PD and the observed default rate). A new model **fails** if, in any segment, the 95% interval of the difference shows it clearly worse (AUC difference entirely below zero, or calibration error difference entirely above zero). It need not improve everywhere. `purpose`, `home_ownership` and `verification_status` are reported in the model card but do not block.
- **Alternatives considered**: (A) global metrics only: a loss in one group goes unseen; (C) many segments: wide watch, but frequent false alarms.
- **Why**: the blocking segments follow how the investor decides (grade, term) and how the world changes (time), with few false alarms.
- **Consequences**: the baseline uses `grade` only, so it gives one PD per grade and its AUC inside a grade is 0.5; the segment test against the baseline is easy to pass, and does its real work for a challenger against the champion.

<a id="d-082"></a>
### D-082 Automatic promotion when every rule passes, with evidence, an alert and a tested rollback

Date: 2026-11-23 · Step: 3.4 · Status: Active

- **Context**: in F4 and F6 the simulation retrains unattended over five simulated years. The rules are strict: better than the champion by more than the noise (D-075), not clearly worse in any key segment (D-081), signs and monotonicity (D-080), and the behavioural tests of step 3.3.
- **Decision**: a challenger that passes every rule becomes champion automatically: the registry alias `champion` moves to it. Safeguards: no rule can be skipped (there is no "force" option); every promotion stores its full evidence in MLflow (intervals, segments, test results); every promotion sends an alert; going back to the previous champion is one command, covered by a test (step 3.4).
- **Alternatives considered**: (B) automatic up to "approved candidate", then a person confirms: human control, but the simulation stops at every retraining waiting, and such approvals tend to be given without looking; (C) shadow mode for some months before promotion: catches operational problems, but gives no evidence of better performance, because labels arrive years later.
- **Why**: the rules are reviewed code, not a judgement made on the day; the simulation must run by itself; any promotion can be undone at once.
- **Consequences**: a bank would add the human approval of B for regulatory reasons; this is a deliberate difference from real production, stated in the model card and the README. The quality of the rules is what makes this safe, so each rule has its own tests, including a deliberately bad model that must fail them (playbook 3.3).

<a id="d-083"></a>
### D-083 The API returns the four main reasons of each prediction; the full SHAP vector is stored with it

Date: 2026-11-23 · Step: 3.5 · Status: Active

- **Context**: SHAP explains one prediction as a base value (the model's mean prediction) plus one contribution per feature, in log-odds, and the contributions add up exactly to the prediction minus the base value. LightGBM computes them itself and for the logistic regression they are coefficient times value, so the API does not need the `shap` library (D-078); one loan takes milliseconds. Platt calibration (D-076) is a straight line in log-odds (`a x prediction + b`), so after it every contribution is multiplied by `a`, the base value becomes `a x base + b`, and the sum still holds.
- **Decision**: the API returns, with each PD, its **four main reasons** (the four largest contributions, with sign). The full vector of contributions and the base value are stored with the prediction in the database.
- **Alternatives considered**: (A) explanations only in reports: the investor sees a PD without knowing why, and a single decision cannot be audited later; (C) the full vector in the API response: hard to read, and the detail is stored anyway.
- **Why**: every decision is explained and can be audited years later, as regulated credit requires (reasons for a refusal), without flooding the user.
- **Consequences**: slightly larger responses and about 30 numbers more per stored prediction. A model test checks, for every model, that base value plus contributions equals the prediction (playbook 3.5).

<a id="d-084"></a>
### D-084 Buy rule: buy when the expected return beats a minimum chosen on validation

Date: 2026-11-24 · Step: buy rule (left open in `problem.md` section 2 until F3) · Status: Active (implemented after the LGD model)

- **Context**: the buy rule turns PD and LGD into "buy / do not buy", and the business metric (D-007) is measured on what it buys. Each loan is decided when it is listed (D-008), so the rule must be a threshold, not "the best of the month".
- **Decision**: buy a loan when its **expected return** is at least a minimum: `expected return = (1 - PD) x scheduled interest - PD x LGD`, where scheduled interest is the total interest of the loan as a share of its amount, from `int_rate` and `term` with the amortisation formula. The minimum is chosen on the validation set. The baseline uses the same rule with its own PD and LGD by grade (D-004, D-005).
- **Alternatives considered**: (A) buy when expected loss (PD x LGD) is below a threshold: simple, but it ignores the interest rate and refuses risky but well-paid loans, exactly what D-002 wanted to capture; (C) the same as the decision plus a prepayment model: more realistic, but a third model, outside the scope agreed in F0.
- **Why**: it weighs risk against return, which is what an investor decides on. Example with LGD 60% and 36-month loans: grade A at 7% (scheduled interest about 11%) and PD 4% gives 0.96 x 0.111 - 0.04 x 0.6 = 0.083; grade E at 20% (about 34%) and PD 25% gives 0.75 x 0.338 - 0.25 x 0.6 = 0.103, a better purchase despite six times the PD.
- **Consequences**: known simplifications, documented in the model card: prepayments (which cut interest) and the instalments a defaulted loan pays before default are ignored, so expected return is overstated, by more for riskier loans. Realised return (D-007) is measured on actual payments, so it is not affected. The budget and how it is spent are a separate decision.

<a id="d-085"></a>
### D-085 Budget: one 25 dollar note per loan, a monthly cap of 10% of last month's listings, idle cash earns nothing

Date: 2026-11-24 · Step: buy rule · Status: Active

- **Context**: D-007 compares portfolios "with the same budget" but does not say how much it is or how it is spent. On Lending Club an investor bought 25 dollar notes of each loan (a share of it), not whole loans. Loans are decided one by one as they are listed (D-008).
- **Decision**: one **25 dollar note** per loan bought. Each month the investor can buy at most **K notes**, with K equal to 10% of the loans listed the month before (known at the time). Loans that pass the buy rule (D-084) are bought in listing order until K is reached. Money not invested counts with a return of zero. Our model and the baseline play by exactly the same rules.
- **Alternatives considered**: (A) one note for every loan that passes, with no cap: simple, compares return per dollar, but the money invested differs, so a very selective rule looks better than it is; (C) amounts proportional to expected return: better use of capital, but it is portfolio management, outside the scope agreed in F0.
- **Why**: the same money, spent the same way, by both investors. Counting idle money at zero stops a rule that buys one safe loan a month from looking excellent: idle cash has an opportunity cost.
- **Consequences**: 10% is a judgement: enough room to be selective without running out of loans to buy; the business metric is also reported at 5% and 20% to show how sensitive it is. Loans out of coverage (D-070) are never bought by either investor.

<a id="d-086"></a>
### D-086 Behavioural model tests: invariance, direction, minimum cases, prediction time, and bad models that must fail

Date: 2026-11-24 · Step: 3.3 · Status: Active (each test approved by Juan before it is written)

- **Context**: the performance tests compare metrics (D-075, D-080, D-081). Behavioural tests check that the model acts with common sense on concrete cases, without looking at metrics. The playbook (3.3) asks for invariance, direction, minimum cases and prediction time, and for a deliberately bad model that fails.
- **Decision**: the battery has five kinds. **Invariance**: changing fields the model does not use (`id`, `emp_title`, `addr_state`) leaves the PD unchanged, and a loan scored alone or inside a batch gets exactly the same PD. **Direction**: on real validation loans, raising each of the nine features of D-080 in its risk direction never lowers the PD (and the reverse for the protective ones). **Minimum cases**: a clearly good profile (grade A, FICO 800, `dti` 5, no delinquencies) gets a lower PD than a clearly bad one; every PD is between 0 and 1; a loan with empty optional fields is scored without error; a loan of a term out of coverage gets no PD (D-070). **Time**: one prediction with its explanation takes under 50 ms (p95) in process, so that the API keeps its 200 ms (`problem.md`). **Bad models**: a constant model and a random model must fail the full battery.
- **Alternatives considered**: (A) direction and bad models only: quick, but batch against single scoring and the edge cases go untested; (C) the battery plus fairness tests by protected group: very relevant in credit, but the data hold no protected attributes, and proxies were handled in F0 (D-018); a separate decision if wanted.
- **Why**: it covers what step 3.3 asks for and shows the tests catch something. A constant model at the mean PD is perfectly calibrated overall, so calibration alone would let it through; it is stopped by the comparison with the baseline (AUC 0.5), by the segment test against the champion and by the minimum cases (a good profile must score lower than a bad one).
- **Consequences**: each test gets its ID in `docs/tests.md` and Juan's approval before it is written (D-057).

<a id="d-087"></a>
### D-087 LGD candidates: regularised linear regression and LightGBM against the mean by grade, with the PD machinery

Date: 2026-11-24 · Step: 3.2 · Status: Active

- **Context**: LGD is hard to predict loan by loan: in the research phase the best model (CatBoost) reached R² 0.064, while its mean level matched (52.2% predicted against 52.2% observed). What matters for expected loss is the level by segment. The baseline is the mean LGD by grade (D-005). At T0 there are about 1,400 matured defaults between training and validation.
- **Decision**: the same machinery as the PD. Candidates: a **regularised linear regression** and a **LightGBM regressor**, tuned on the inner split (D-073, D-074), compared with the mean by grade on validation with the paired bootstrap of D-075 on RMSE, and with the calibration by segment of D-081 (mean predicted against mean observed LGD). Predictions are clipped to [0, 1]. Same split by term (D-069). If no candidate beats the baseline by more than the noise, the mean by grade is the LGD champion.
- **Alternatives considered**: (A) the baseline only, never challenged: simple, but a model that beats it with more data would never be found; (C) LGD-specific models (beta regression, two-stage models: does it recover anything, and how much): closer to the shape of LGD, but more complex, and they did not win in the research phase.
- **Why**: it reuses every rule already decided, and lets the data of each date say when a model beats the mean by grade. A mean by grade as LGD champion at T0 is an honest result, not a failure.
- **Consequences**: the champion/challenger logic must also accept a baseline as champion. The level by grade matters even with a low R², because expected loss multiplies it: a level error in one grade shifts the expected loss, and the buy decision, of every loan in that grade.

<a id="d-088"></a>
### D-088 The LGD label is a column of the training file, computed when the snapshot is built

Date: 2026-11-24 · Step: 3.2 (changes step 2.3, D-060) · Status: Active (implemented in the first F3 pull request, data)

- **Context**: a snapshot has two files (D-060): `features.parquet`, the only one training reads (features and the default label), and `evaluation.parquet`, with payments and recoveries, read only by evaluation. LGD is computed from payments and recoveries (data audit, section 4.5), so LGD training had no label.
- **Decision**: `features.parquet` gets an `lgd` column, computed when the snapshot is built: `(EAD - principal repaid - (recoveries - collection fee)) / EAD`, with EAD the funded amount, only for loans charged off at least 12 months before T (D-017); empty for every other loan. Values outside [0, 1] are kept as computed and clipped by the model step.
- **Alternatives considered**: (B) LGD training also reads `evaluation.parquet`: no change to F2, but it breaks the guarantee of D-060, since training code would have future payments at hand and a mistake could turn them into features; (C) a separate LGD snapshot: full separation, but two data versions per training to keep in step.
- **Why**: the same reasoning as for the default label: a label may come from the future because it is what is predicted, never an input. The raw payment columns could be used as features by mistake; one derived number for the eligible loans only cannot.
- **Consequences**: `sql/training_ids.sql` (or its companion query), the snapshot schema and test T5.5 change (test changes need Juan's approval); every snapshot gets a new content hash (only test snapshots exist so far). The rule of D-017 lives in one place, versioned with the snapshot.

<a id="d-089"></a>
### D-089 F3 is delivered in three pull requests: data, training, explanation and business

Date: 2026-11-24 · Step: F3 (cross-cutting; adjusts the one-pull-request-per-phase default of the way of working) · Status: Active

- **Context**: F3 is far larger than F2: snapshot changes, PD and LGD training, MLflow, two images, model tests, registry, explainability, model card and buy rule. Juan reviews every pull request.
- **Decision**: three pull requests, in order. (1) **Data**: validation split per term (D-069) and the `lgd` label (D-088). (2) **Training**: PD and LGD, MLflow, the `serve` and `train` images, model tests, registry and promotion. (3) **Explanation and business**: SHAP, the model card, the buy rule and the business metric. The tests of each pull request are proposed to Juan, group by group, just before they are written.
- **Alternatives considered**: (A) one pull request at the end, as in F2: one review, but thousands of lines at once, and a problem found early surfaces only at the end.
- **Why**: each pull request makes sense on its own and carries its tests; reviews stay thorough; failures appear sooner. The data pull request goes first because training reads the snapshot it changes: training on the old split or without the LGD label would be work thrown away.
- **Consequences**: three reviews and three CI runs. After each merge the work branch restarts from `main`.

<a id="d-090"></a>
### D-090 With no PD champion yet, the first model must beat the grade-only baseline; otherwise the baseline is the champion

Date: 2026-11-24 · Step: 3.4 · Status: Active

- **Context**: promotion (D-082) compares a challenger with the champion, but at the first training there is no champion. For the LGD, D-087 already lets the mean by grade be the champion. For the PD this was not written down. Found while proposing test T11.5.
- **Decision**: when there is no PD champion, the chosen model is compared with the grade-only logistic regression (D-004) under the same rules as any promotion: paired bootstrap (D-075), segments (D-081), signs (D-080) and the behavioural battery (D-086). If it passes, it becomes the first champion. If not, the baseline is registered and becomes the champion, and the next retraining competes against it.
- **Alternatives considered**: (A) the first model becomes champion without comparison: simple, but a model no better than the grade alone could start buying; (B) no champion until a model beats the baseline, so nothing is scored: the simulation stops buying for no reason, when the baseline is a valid model that the business metric already uses as reference (D-084).
- **Why**: the same rule as the LGD (D-087) and as every later promotion; nothing enters production without beating what it replaces, and something always does the scoring.
- **Consequences**: the baseline is trained, logged and registered like any model, with the same required fields (D-079). The battery for the baseline has to accept that its PD is constant inside a grade: every test of D-086 applies as it is, and the direction test passes without effort for the features the baseline does not use, because its PD does not move with them. Each promotion writes on the new model version a tag with the previous champion and the date, so that rollback (T11.4) and the history of champions do not depend on the registry alias, which keeps only the current one.

<a id="d-091"></a>
### D-091 The MLflow server of docker compose runs from our `train` image

Date: 2026-11-24 · Step: 3.2 (completes D-079) · Status: Active

- **Context**: D-079 puts an MLflow tracking server in docker compose, with its metadata in Postgres, but does not say which image it runs from. The `train` image (D-078) already carries the full MLflow and a Postgres driver (`psycopg`).
- **Decision**: the `mlflow` service of docker compose runs `mlflow server` from our `train` image. It is built by `make build` before `make up`.
- **Alternatives considered**: (B) the official MLflow image, pinned by version and digest: an external image to keep up to date apart from `uv.lock`, and, as far as known, without a Postgres driver, so it would need a Dockerfile of its own to extend it (not checked: Claude's cloud machine cannot download from ghcr.io).
- **Why**: the server and the client that logs the runs have the same MLflow version always, fixed in `uv.lock` and updated by Dependabot with everything else; no new image to pin and scan.
- **Consequences**: `make up` needs the `train` image built first; CI builds it before starting compose. The server image is scanned by Trivy with the `train` image.

<a id="d-092"></a>
### D-092 The logistic regression keeps the signs of D-080 by removing a wrong-signed feature and refitting

Date: 2026-11-24 · Step: 3.2 (completes D-080) · Status: Active

- **Context**: in the first training on the real data at T0 (2026-11-24), the logistic regression gave two of the nine features of D-080 the wrong sign: `pub_rec` (-0.04 per standard deviation) and the length of credit history (+0.01). The first is almost surely collinearity: `pub_rec > 0` and having `mths_since_last_record` are nearly the same thing, and the indicator of that gap takes the effect (raw default rate 21% with one public record, 13% with none). The second is practically zero. Under D-080 the logistic regression would fail and could never be champion, while D-068 picks it on a tie: the two rules clashed.
- **Decision**: the signs are enforced while fitting. While a feature of D-080 gets a coefficient with the wrong sign, the one with the largest wrong coefficient is removed and the model is fitted again, until every sign holds. The same procedure is used in the search (D-074) and in the final fit. The removed features are logged with the run.
- **Alternatives considered**: (B) the same effect with an optimiser that bounds each coefficient (at least or at most zero), instead of scikit-learn: more code of our own to test and maintain; (C) let the logistic regression fail and write a rule for when the simpler model fails: a model a bank would never accept goes on being trained at every retraining.
- **Why**: it is the standard practice in bank scorecards, it uses scikit-learn as it is, and it leaves on record which features left and why. It is the counterpart of the monotone constraints of LightGBM.
- **Consequences**: the sign test of D-080 now checks the procedure (it must never return a wrong sign) as well as each model. A feature removed at one date may come back at the next retraining, with more data.

<a id="d-093"></a>
### D-093 A key segment blocks a promotion only if it is clearly worse by more than a margin

Date: 2026-11-24 · Step: 3.3 (amends D-081) · Status: Active

- **Context**: in the first retraining on the real data at T0 (2026-11-24), the logistic regression beat the grade-only baseline clearly in AUC (improvement +0.04, interval [+0.021, +0.062]) but D-081 rejected it: in the segment of grades D to G its calibration error was 0.66 points of PD against 0.11 for the baseline, an interval of the difference of [-0.97, -0.12] points. Statistically clear, practically tiny. The baseline is a rate per grade, so inside each grade it is calibrated almost perfectly by construction. Worse, intervals narrow as data grow (140,000 validation loans in 2018), so any difference of a tenth of a point would become "clear" and almost no promotion would pass.
- **Decision**: a segment blocks only if the new model is worse for sure **and** by more than a margin: the whole 95% interval of the improvement lies below minus the margin. Margins: **0.01 of AUC** and **1 point of PD** in calibration error for the PD; **2 points of LGD** in calibration error for the LGD. The margins are fixed in code and logged with the evidence of every promotion.
- **Alternatives considered**: (B) judge calibration in a segment in absolute terms: the model's mean PD must lie inside the interval of the observed default rate of the segment; purer, but with many loans those intervals are very narrow and it would fail for differences just as small; (C) keep D-081 as it was: at T0 the baseline would be champion, and with more data almost no model could be promoted.
- **Why**: it separates what is statistically clear from what matters, which is how tolerances are set in model validation at banks. A real worsening still blocks.
- **Consequences**: with the margins the logistic regression is promoted at T0. Test T9.3 checks the rule with a model clearly worse in grade A (blocked), a tie (passes) and a model clearly worse but within the margin (passes).

### D-094 The level of every LGD model is corrected on validation, like Platt scaling for the PD

Date: 2026-11-24 · Step: 3.2 (amends D-087) · Status: Active

- **Context**: in the data test T12.6 at T0 (2026-11-24) the LGD champion, the mean by grade, predicted a mean LGD of 0.592 in validation against 0.642 observed (95% interval [0.620, 0.664]). Ridge and LightGBM were just as low. The LGD rises with the listing year: 0.50 for 2007 loans, 0.57 for 2008, 0.60 for 2009, 0.62 for 2010 in training and 0.64 for 2010 in validation. A model fitted on every year of training averages them and lags the latest ones. Underestimating the loss inflates the expected return of every loan, so the buy rule of D-084 would take more risk than it believes. RMSE does not show it: every model lags by the same amount.
- **Decision**: after fitting on training, every LGD model, the baseline included, gets a level correction fitted on validation: one number, the observed mean LGD minus the mean predicted, added before clipping to [0, 1]. Candidates are compared, and the champion chosen, with their corrected predictions. The correction is logged as the tag `level_shift` of each run. The calibration error logged for each LGD run is cross-fitted within validation (five folds), as D-076 does for the PD, because on validation the corrected level is right by construction (E-036).
- **Alternatives considered**: (B) give more weight to recent years in training: reduces the lag but does not remove it, and adds a weight to choose; (C) leave the model as it is, record the failing check as expected and let the monitoring of F6 watch the level.
- **Why**: it is the same logic Juan chose for the PD (D-076): the shape is learned on training and the level is set on the most recent period with known outcomes. One number keeps it simple and cannot change the order of predictions.
- **Consequences**: at T0 the shifts are +0.050 (ridge), +0.054 (LightGBM) and +0.050 (baseline); validation RMSE goes from 0.221 to 0.216 for each; no candidate beats the baseline, which stays champion. On validation the mean predicted equals the observed mean by construction, so it can no longer be a check of the level: T12.6 changes, with Juan's approval. With a rising trend the model can still lag by the change between the validation window and the time it is used; the monitoring of F6 compares the predicted and observed LGD of each new group of resolved defaults.

### D-095 A model card is generated for every registered version and stored with it

Date: 2026-11-24 · Step: 3.5 · Status: Active

- **Context**: a model card states what a model is for and not for, the data it was trained on, how it performs overall and by segment, its known limits and which features weigh most. It is the first document a model validator asks for. Models here are retrained and promoted automatically (D-082), so a document written by hand would be out of date after the first retraining.
- **Decision**: every registered version gets a `model_card.md` in the artefacts of its run, built from what the run recorded: training set version and dates, counts, metrics with intervals, segment results, battery, signs and removed features (D-092), LGD level shift (D-094), global importance (mean absolute SHAP contribution on validation, D-083). The parts that do not come from data (intended use, uses not intended, features left out on purpose, known limits) are fixed text in the code, reviewed in every pull request. A copy of the card of the first champion (T0) is kept in `docs/`.
- **Alternatives considered**: (B) a card written by hand in `docs/`: easier to read, stale at the first retraining; (C) only the model description in MLflow: no structure, no segments.
- **Why**: each version that can become champion carries its own card, and the card can never disagree with the model it describes.
- **Consequences**: one more artefact per run; its content is checked by tests.

### D-096 The realised return is measured on the 12 months after T0; validation only chooses the minimum of the buy rule

Date: 2026-11-24 · Step: 3.5 (completes D-007, D-084, D-085) · Status: Active

- **Context**: the minimum expected return of the buy rule (D-084) is chosen on validation. Measuring the realised return (D-007) on the same loans would report a result fitted to them, so optimistic.
- **Decision**: the business metric of F3 is measured on the loans listed in the 12 months after T0 (February 2014 to January 2015), with their final outcomes from the later deliveries, as an investor using the T0 models for a year would have earned. Validation only chooses the minimum, for our models and for the baseline alike. The later outcomes are used to measure, never to design or choose anything.
- **Alternatives considered**: (B) cross-fitting within validation: choose the minimum on four fifths and measure on the fifth left, five times; nothing after T0 is used, but only six months of loans; (C) validation alone: simplest, but optimistic.
- **Why**: it is the honest answer to "would it have made more money?", with both investors under the same rules and budget (D-085).
- **Consequences**: the measurement needs every delivery up to the end of those loans, so it is a data test (local). It is a single year with a single pair of models; F4 and F7 repeat it as the models are retrained.

### D-097 The business result at T0 is reported as measured; improving the buy rule is a later decision

Date: 2026-11-24 · Step: 3.5 (follows D-096) · Status: Active

- **Context**: T15.7 measured the realised return at T0 (D-096) on the loans listed from 2014-02 to 2015-01, with the same budget for both investors. Our models do not beat the grade baseline: +8.99% against +8.95% at a cap of 5%, +8.46% against +8.95% at 10%, +7.49% against +8.70% at 20%. Our investor chooses a higher minimum on validation, buys fewer notes (idle money earns zero) and the notes it buys default more often. A better PD ranking (AUC 0.677 against 0.636) does not turn into better choices under this rule.
- **Decision**: the result is reported as measured in the README, the technical document and the known limits of the model card, and the third pull request of F3 is opened with it. Looking for the cause and changing the buy rule is a separate decision, with its own tests, after this pull request.
- **Alternatives considered**: (B) investigate the cause before opening the pull request; (C) change the buy rule now (for example, rank by expected return and fill the cap), with new tests.
- **Why**: the measurement was designed before the result was known and is closed; changing the rule after seeing the answer, on the same year, would fit the rule to that year. A negative result stated plainly is worth more than one fixed without evidence.
- **Consequences**: the claim of the project at T0 is that the models rank and are calibrated better than the baseline, not that they earn more. The buy rule is open for review in a later step; any new rule is measured on loans it was not chosen on.

### D-098 Scope of F4: the orchestrated training flow and a simulated clock; batch prediction (step 4.2) moves to F5

Date: 2026-11-24 · Step: F4 · Status: Active

- **Context**: the playbook puts two steps in F4: 4.1, an orchestrated training flow, and 4.2, a batch flow that scores each month with the champion. D-008 decided in F0 that the API is the only prediction path: a replayer sends each month's loans to the API, and no monthly batch scores them again. The API arrives in F5.
- **Decision**: F4 is step 4.1 plus a simulated clock, a command that moves the system forward month by month (publish, load and validate, version and, when due, retrain and promote). Step 4.2 moves to F5 as the replayer that calls the API and stores the predictions. F4 is delivered in two pull requests: (1) the flow and the orchestrator in docker compose, with their tests; (2) the clock, the retraining cadence and the alerts.
- **Alternatives considered**: (B) build the predictions table and score in process now, and switch to the API in F5: two prediction paths for a while, against D-008; (C) step 4.1 only, without the clock: a smaller pull request, but the system does not yet live through time.
- **Why**: it keeps D-008 (a single prediction path) and closes F4 with a system that moves through time and retrains without anyone touching it.
- **Consequences**: the tracking sheet marks 4.2 as replaced by the F5 replayer.

### D-099 Orchestrator: Prefect 3

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: step 4.1 asks for a flow that runs on its own, with retries, a schedule, a record of every run and alerts on failure. Cron only gives the schedule.
- **Decision**: **Prefect 3**. Flows and tasks are plain Python functions with decorators; a server in docker compose keeps the history and the web interface; a worker runs our code.
- **Alternatives considered**: (B) Airflow 3: the industry standard and the most asked for in job offers, but four or five more services (API server, scheduler, DAG processor, triggerer, a database migration job), at least 4 GB of memory, an image of its own over 1 GB, and either access to the Docker socket (whoever controls it controls the machine) or a second Python environment inside its image; (C) Dagster: its "assets" fit the versioning of F2 well, but a steeper learning curve and few job offers; (D) cron and make: no retries, history or interface.
- **Why**: it covers everything step 4.1 asks for with little infrastructure, and a flow reads as Python, so the logic stays in `src/` and the flow only coordinates. Juan asked how much more infrastructure Airflow meant (the numbers above) before choosing.
- **Consequences**: two more services in compose (server and worker); see D-103 for how Prefect is installed.

### D-100 Tasks are cut where their result is stored; only identifiers travel between them; PD and LGD apart

Date: 2026-11-24 · Step: 4.1 · Status: Active (amended by D-105: the publish task left the flow)

- **Context**: a task is what Prefect retries, records and lets fail on its own. Every existing command already stores its result: `publish` (files), `ingest` (raw, validation, clean), `snapshot` (versioned training set), `train` (PD and LGD, registry, promotion).
- **Decision**: one task per stored result, with the PD and the LGD as separate tasks. Between tasks only identifiers travel (a month, a training set version, a registered version, the covered terms), never data. `retrain()` is split into `retrain_pd()` and `retrain_lgd()`; the LGD receives the terms the PD covers, as before.
- **Alternatives considered**: (A) four tasks, one per command: no change to `src/`, but a failure in the LGD retrains and registers the PD again; (C) about ten fine tasks: more detail, but it breaks transactions that are one on purpose (a month is validated and written to clean at once, D-049, D-055) or forces data between tasks.
- **Why**: every cut matches something already persisted, so a retry is safe and cheap, and a failure of one model does not repeat the other.
- **Consequences**: the flow of PR 1 has four tasks (`load`, `version`, `train-pd`, `train-lgd`, D-105). The retraining cadence (PR 2) decides when the last three run.

### D-101 Training is idempotent by a key kept in MLflow: model, training set version and code commit

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: with automatic retries a task can run twice, and the second run may come after the first did half its work. Publishing, loading and versioning were already idempotent (D-049, D-061). Training was not: running it again created new runs and registered another version of each model.
- **Decision**: every registered version carries the tags `training_set`, `commit` and `role` (`challenger` or `baseline`). Before training, the task looks for a registered challenger with the same model, training set and commit; if found, nothing is trained and the registered version is reused. A training that logged runs but never registered its model does not count: it is trained again, and the runs left behind are marked `FAILED` and `orphan`. The promotion is idempotent too: the verdict, its evidence and what it was taken against are written first (`promotion.decision`), then the alias moves, then `promotion.outcome` is set; calling it again returns the stored verdict, and a promotion that stopped after deciding is carried out without judging again. The baseline is registered before the challenger, so a registered challenger means everything it needs is registered.
- **Alternatives considered**: (B) Prefect's result cache on the task inputs: almost no code, but the truth would live in Prefect's database; if it were lost, or if someone ran `make train` without Prefect, models would be duplicated again; (C) accept duplicates and let the promotion reject identical models: the registry fills with copies and the playbook test "running again does not duplicate" fails.
- **Why**: the guarantee lives with the models and in `src/`, works the same with or without the orchestrator, and is tested by unit tests.
- **Consequences**: a change of code (a new commit) retrains on the same data, as it should: it is another procedure. Images carry their commit (`CREDIT_RISK_COMMIT`, passed by `make build` and CI), because the key needs it.

### D-102 Only transient failures are retried: 3 attempts after 10, 30 and 90 seconds

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: a failure is either transient (Postgres or MLflow do not answer for a moment; trying again usually works) or permanent (a critical validation failure, a malformed delivery, a checksum that does not match: trying again gives the same error, later). Retrying a permanent failure only delays the alert and, in training, spends minutes of computing again.
- **Decision**: Prefect's `retry_condition_fn` lets each exception decide. Retried: `psycopg.OperationalError` and MLflow requests that got no answer, timed out or got a 5xx answer; 3 attempts after 10, 30 and 90 seconds. Anything else stops the flow at once, including an error nobody foresaw: a needless alert costs less than a blind retry. The list is in `credit_risk.flows.is_transient`, with its tests.
- **Alternatives considered**: (A) the same retries for everything: simplest, but a validation failure is repeated three times and the alert comes late; (C) no retries: honest, but a one-second network cut at night leaves the month unprocessed until someone relaunches.
- **Why**: the flow stops dead on bad data, as the playbook asks, and rides out short cuts without help.
- **Consequences**: the alert on failure is designed in PR 2.

### D-103 Prefect in the `train` group, accepting three version downgrades; server and worker from the `train` image

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: Prefect 3.9.4 (the latest) was added to the `train` group in a trial. It brings 49 packages and forces three downgrades in the whole lock: FastAPI 0.165 to 0.150 (Prefect asks for `<0.151`; MLflow's server uses it now, and the API of F5 will be built on it), python-dateutil 4.0 to 2.9 (`<3`) and python-slugify 9.2.0 to 9.1.3. `pip-audit` on that lock found no known vulnerability.
- **Decision**: Prefect goes into the `train` group and the downgrades are accepted. The Prefect server and the worker run from our `train` image, like the MLflow server (D-091); the server keeps its metadata in a database `prefect` of the project's Postgres, created at start-up if missing.
- **Alternatives considered**: (B) Prefect isolated in its official image, with a Docker worker that starts our `train` container for each task: our lock is untouched, but the worker needs the Docker socket, the flow calls containers instead of Python, and tests are slower; (C) two Python environments in one image, Prefect's and ours, with tasks calling commands: isolation without the socket, but two locks to keep in step.
- **Why**: minor downgrades with no known vulnerability, one environment, and the flow calls `src/` directly.
- **Consequences**: the API of F5 starts on FastAPI 0.150 until Prefect relaxes its limit; Dependabot will show when it does. The `train` image grows to 1,387 MB of its 1,500 MB budget (B5). B7 checks that `serve` cannot import Prefect.

### D-104 The load task catches up every delivered month up to the one asked

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: the load task receives a month. It can load only that month, or also any earlier month that is missing or changed.
- **Decision**: it goes through every delivered month up to the one asked, oldest first. A month already loaded from the same files is skipped by its hash (D-049); a corrected delivery is loaded again; a month that failed before is tried again, and if it fails again the flow stops before versioning. The history before T0 is loaded by the first run.
- **Alternatives considered**: (A) only the month asked: more direct, but a month that failed and was never relaunched leaves a gap, the next month loads anyway and the training set is built over the gap; the history before T0 needs loading apart.
- **Why**: a training set is never built over a gap or an old delivery, the silent error that costs most to find.
- **Consequences**: each run writes about 280 `unchanged` lines in `ops.ingest_log` (about 17,000 over the five simulated years) and spends a fraction of a second per month on hashes (measured: 0.2 seconds for 56 unchanged months).

### D-105 Publishing deliveries is not a task of the system's flow (D-043 kept)

Date: 2026-11-24 · Step: 4.1 (amends D-100) · Status: Active

- **Context**: the first version of the flow had a `publish` task that called the simulator. T1.11 failed: D-043 says only the simulator opens the 2019 file and system code never imports the simulator.
- **Decision**: the system's flow has four tasks and starts from the deliveries that have arrived in the landing folder, as it would with a real provider. Publishing belongs to the simulated world: `make flow PERIOD=...` runs the simulator first, the clock of PR 2 will do the same, and the tests publish before running the flow. D-043 and T1.11 are unchanged.
- **Alternatives considered**: (B) keep five tasks and relax D-043 so that the flow, and only the flow, may import the simulator: more convenient, but the system would be tied to something that would not exist in production, and T1.11 would change.
- **Why**: it is what D-043 is for: if a real provider replaced the file, the simulator would be thrown away and the system's flow would not change.
- **Consequences**: D-100 amended (four tasks in the system); T16.7 and T16.10 changed wording (the test publishes; the failing deployment run fails in `load`).

### D-106 Retraining every quarter (January, April, July, October); every month is loaded

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: the flow loads and validates every month. The cadence decides in which months it also versions a training set and retrains the PD and the LGD. Each month adds only one matured cohort (the 36-month loans listed 41 months before), so the training set grows little from one month to the next, and a full-scale retraining (up to about 500,000 loans and 50 Optuna trials) can take minutes. The simulation runs 60 months, 2014-01 to 2018-12.
- **Decision**: retrain in January, April, July and October (20 retrainings in the simulation). The cadence is a parameter of the flow and of the clock (`monthly`, `quarterly`, `yearly`; anything else is refused); `quarterly` is the default. A month that does not retrain runs only the `load` task. F6 adds retraining triggered by drift.
- **Alternatives considered**: (A) every month: the freshest, but each challenger is almost the champion, promotion rejects it as within the noise, and the registry fills with versions that add nothing; (C) every year, as in a bank's annual model review: the system would barely show its improvement cycle in five years, and a change in 2015 could take a year to be noticed; (D) none fixed, only when the monitoring of F6 asks: until F6 the clock would never retrain, and F4 would not show the whole cycle.
- **Why**: each challenger brings three new cohorts and a real chance of improving; compute and registry stay reasonable; new fields (D-016) enter with three months of delay at most. A fixed calendar plus a trigger on evidence is the usual pattern: the calendar keeps a model from ever getting too old, the trigger reacts sooner when something changes.
- **Consequences**: `flows.retrains(period, cadence)`; the flow returns early, after `load`, in the other months (`"retrained": False` in its summary). Tests T17.1 and T17.6.

### D-107 The simulated clock: an "advance one month" flow with its state in `sim.clock`

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: in production the calendar is real: on the first of each month the orchestrator runs the flow for the month that has just arrived. In the simulation something must say what "now" is, keep it, and move it. The clock belongs to the simulated world, like the simulator (D-043): it publishes the next month's delivery and then runs the system's flow for that month.
- **Decision**: a flow `advance` (in `credit_risk/simulator/clock.py`) reads the last completed month from `sim.clock`, publishes the next one (the whole history on the first run, from 2014-01, D-041), runs the system's flow for it as a subflow and only then writes the month as done. If anything fails the clock does not move, and the next `advance` tries the same month again: a month is never skipped nor done twice. A flow `replay` calls `advance` until a given month. Both are deployments served by a new compose service, `clock`; `advance` has an interval schedule (one simulated month every 10 real minutes), paused by default. `make advance` and `make replay TO=YYYY-MM` run them through the server; they replace `make flow` of PR 1. The table lives in a schema of its own, `sim`, that the system never reads.
- **Alternatives considered**: (A) only a replay command looping over months: simple and deterministic, but "now" is kept nowhere (after a failure in 2016-03 someone has to remember to start again there), and it does not use the orchestrator's scheduling, which the playbook asks for; (B) only a Prefect schedule moving one simulated month every N real minutes: shows periodic scheduling, but replaying five years takes hours, and tests and demos need a faster way.
- **Why**: the stored state means the clock never skips or repeats a month, and the same flow serves the scheduled demo and the fast replay.
- **Consequences**: `publish` takes `since`, so a month delivers only its own files. The worker no longer mounts `data/landing`: deliveries arrive in the shared volume through the clock. Tests T17.3 (no system module mentions `sim`), T17.4, T17.5, T17.8 and T17.9.

### D-108 Alerts recorded in `ops.alerts`; the channel that delivers them is chosen in F6

Date: 2026-11-24 · Step: 4.1 · Status: Active

- **Context**: an alert has two parts: recording the event (what, when, which month and task, which error) and getting it to a person (email, Slack, phone). Step 4.1 asks for an alert when a flow fails; a change of champion, by promotion or rollback, was until now a WARNING line in the log (D-082).
- **Decision**: one table, `ops.alerts`, records four kinds of event: `flow_failed` (severity error, written by an `on_failure` hook of the system's flow, with the month, the failed task and the error), `promoted` (warning: model, new version, previous champion), `rejected` (info, with the failed rules) and `rolled_back` (warning, written by `python -m credit_risk.registry rollback`). A verdict on a version is recorded once however many times its month runs (unique index on kind, model and version for promotions and rejections). Grafana reads the table in F6 and sends the alerts through the channel chosen then, together with the drift alerts. Until then they are read with SQL or in the Prefect UI.
- **Alternatives considered**: (A) only logs and the Prefect UI: free, but nobody finds out without looking, and there is no record to query; (C) the table plus a webhook now (Slack, Discord or ntfy.sh): the alert really arrives from today, but needs a webhook kept as a secret, leaves two alert paths in F6, and the real sending cannot be tested in CI; (D) Prefect automations (rules on the server): native and without code of ours, but they only see what Prefect sees (not a promotion or a rollback), and their configuration lives on the server, not in the repository.
- **Why**: one record of events that everything writes and F6 reads; the channel is decided once, with Grafana, for failures, promotions and drift together.
- **Consequences**: module `credit_risk/alerts.py`; `registry.rollback` takes a `notify` callback. Tests T17.2 and T17.7.

<a id="d-109"></a>
### D-109 Scope of F5 and three pull requests: the API, the replayer, the published image

Date: 2026-11-24 · Step: F5 · Status: Active

- **Context**: the playbook puts two steps in F5: 5.1, the API, and 5.2, a published image with continuous delivery. D-098 moved here the old step 4.2: a replayer that sends each month's loans to the API (D-008), with every prediction stored.
- **Decision**: F5 is delivered in three pull requests, in order: (1) the API and the `serving` tables; (2) the replayer, inside the simulated clock; (3) continuous delivery of the image.
- **Alternatives considered**: (B) two pull requests, the API and the replayer together: fewer reviews, but a very large first one; (C) one pull request: hard to review in depth.
- **Why**: each pull request has one goal and is reviewable, as in F3 and F4; the replayer builds on an API that is already reviewed.
- **Consequences**: the tracking sheet marks 4.2 as delivered by the second pull request.

<a id="d-110"></a>
### D-110 The API loads the champions from the MLflow registry by their alias

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: the flow of F4 promotes models every quarter by moving the alias `champion` in MLflow. The API needs the champion PD and LGD. The model can travel inside the image or be fetched from the registry.
- **Decision**: the API asks the registry which versions the alias `champion` points to and loads them (`registry.load`, already tested in `serve` by B8). Every answer carries the registered versions it used.
- **Alternatives considered**: (A) the model inside the image: immutable and independent of MLflow, but every promotion needs a new image and a deployment, which breaks the automation of F4 and mixes the life cycle of the code with that of the model; (C) the registry with a local copy as fallback: more resilient, but more code and the risk of silently serving an old model.
- **Why**: a promotion reaches the API without touching the image; the registry is the only source of truth. Usual where models are retrained often.
- **Consequences**: the API depends on MLflow to start serving: until it has loaded the champions `/health` answers 503 (D-111 decides how it learns of new ones).

<a id="d-111"></a>
### D-111 A new champion reaches the API by a notice from the flow, with polling as the safety net

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: in the simulation the clock promotes in month m and the replayer sends the loans of month m right after. If the API still used the old model, those predictions would carry the wrong one.
- **Decision**: after any change of champion the monthly flow calls `POST /admin/reload` (task `reload`, never retried, never failing the flow; a failure is a `reload_failed` alert). Every `API_RELOAD_SECONDS` (60 by default) a thread of the API also asks the registry whether an alias moved. The PD, the LGD and the buy rule are loaded first and swapped in one assignment; a request takes the set once, so it never mixes versions. A load that fails keeps the set in use and records a `model_load_failed` alert, once while the same failure repeats. One process per container, since the notice must reach the process that serves: the API scales by containers.
- **Alternatives considered**: (A) only at start: a restart after each promotion; (B) only polling: up to a minute with the old model, and a simulation that is not deterministic; (C) only the notice: if it is lost, the old model stays indefinitely.
- **Why**: the notice makes the simulation deterministic; polling covers a lost notice.
- **Consequences**: `credit_risk/api/champions.py`; two new alert kinds (migration `20261124180100`); the worker gets `API_URL` and `API_ADMIN_KEY`. Tests T18.8, T18.9 and T19.2.

<a id="d-112"></a>
### D-112 The API returns the risk, the expected return and whether it passes the buy threshold; the monthly cap stays with the investor

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: the buy rule (D-084, D-085) has a part without state, the expected return against a minimum, and a part with state, the cap of K notes a month in order of arrival.
- **Decision**: for each loan the API returns PD, LGD, EAD (the amount of the listing, `loan_amnt`), expected loss `PD x LGD x EAD` and its rate `PD x LGD` (problem.md, section 3), expected return, the minimum and whether the loan passes it, the four reasons (D-083) and the versions. The monthly cap is applied by the investor, on the side of the replayer.
- **Alternatives considered**: (A) only the risk: a pure risk service, but the rule validated in F3 would live elsewhere and could drift from it; (C) the whole decision with the cap: an API with state, hard to scale and to test, mixing risk with portfolio management.
- **Why**: the usual split: the risk service scores and recommends, the portfolio manages the budget. The rule validated in F3 stays next to the models that justify it, and the API keeps no state.
- **Consequences**: the minimum has to be stored with the champions (D-120).

<a id="d-113"></a>
### D-113 `serving.predictions`: one row per prediction, columns for what is filtered, jsonb for what is audited

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: each prediction is stored to audit a decision years later (D-083), to monitor drift and performance in F6 and to know which model made it. About two million rows in a full simulation.
- **Decision**: one row per prediction in the schema `serving`: loan id, listing month, versions of PD, LGD, buy rule and API, coverage, PD, LGD, EAD, expected loss and rate, expected return, minimum and verdict, base value, as columns; the four reasons, the 30 features the model saw, the SHAP contributions and the request as delivered, as jsonb. Checks in the table: PD and LGD between 0 and 1, and a covered loan has its whole risk while an uncovered one has none.
- **Alternatives considered**: (B) normalised in three tables: a strict schema, but about 60 million rows of contributions and joins everywhere; (C) only the outputs in the database and the inputs in Parquet files: a small database, but auditing crosses two stores and the two are not written in one transaction.
- **Why**: the usual inference log: fast queries for monitoring on columns, a complete audit in one row, and drift measured in F6 on the exact features the model saw, never recomputed.
- **Consequences**: migration `20261124180000`; about 5 to 8 GB for the whole simulation. Test T18.11.

<a id="d-114"></a>
### D-114 A loan is stored once per pair of models (unique key in the database)

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: a month of the replay may be sent again after a failure, and a client may retry after a timeout. Scoring the same loan again after a change of champion is legitimate (problem.md, section 4).
- **Decision**: a unique constraint on (loan id, PD version, LGD version). A repeat is not written: the API answers the stored prediction, marked `stored_earlier`. A new champion writes a new row.
- **Alternatives considered**: (B) an `Idempotency-Key` header per request: standard in payments, but it depends on the client, and two different requests for the same loan and models would still duplicate; (C) one row per loan, overwritten: loses which model scored the loan when it was listed; (D) the replayer checks first: the guarantee depends on one client, and the simulated world would read system tables.
- **Why**: the guarantee lives where it cannot be skipped, the database, and fits deterministic models: same input and same models give the same prediction.
- **Consequences**: a second identical request has no prediction row of its own; its request row records it (D-115). Test T18.6.

<a id="d-115"></a>
### D-115 Every request: a JSON log line and a row in `serving.requests`; rejected ones keep body and errors

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: some requests produce no prediction: invalid input (422), refused keys (401, 403), a database that is down (503). How many there are and why is part of data quality (F6) and of debugging.
- **Decision**: every request writes one JSON line to standard output (request id, path, status, latency, client, versions; never a key nor a body). Every request to `/predict`, `/predict/batch` and `/admin/reload` also writes a row in `serving.requests` (id, time, endpoint, client, status, latency, loans, rejected, versions); only a rejected one keeps its body and its errors. Each prediction points to its request. `/health` is only logged.
- **Alternatives considered**: (A) only the log lines: standard for operations and free, but they cannot be queried with the predictions and containers rotate them away; (C) the body and answer of every request in a table: duplicates `serving.predictions` and doubles its size.
- **Why**: the log serves the operator at the moment; the table serves monitoring and the audit of what was refused. Free text of valid requests (the loan description) is kept only with its prediction.
- **Consequences**: tests T18.3, T18.11 and T18.12.

<a id="d-116"></a>
### D-116 The API takes listings as the provider delivers them and cleans them with the code of the monthly load

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: a listing can arrive as the provider publishes it (text such as `" 36 months"`) or already clean (36). This decides whether the API reuses the cleaning of F2.
- **Decision**: a Pydantic model with the columns of the delivery contract as text (strict: a number instead of text is refused). The columns the features read (`features.INPUTS`) must be present, their value may be null; the rest are optional; unknown columns are refused. Then `cleaning.convert` with the rules of the contract and `features.build_features`, the functions of training. A value that does not fit its rule is a 422 with the column, the rule and the value.
- **Alternatives considered**: (B) clean, typed fields: a nicer API, but someone must clean first, so cleaning is duplicated or moved to the client, the skew D-045 and D-008 avoid; (C) a free dictionary checked only by pandera: no schema in the OpenAPI documentation and less clear errors.
- **Why**: one cleaning path for the batch load and for real time (D-045); refusing unknown columns makes a silent change of the provider a visible error.
- **Consequences**: `cleaning.convert` returns the typed frame and the rows that fail each rule, used by `clean` (which stops) and by the API (which rejects only those loans). The month rules of pandera (volumes, history) stay in the monthly load. Tests T18.3 and T18.15.

<a id="d-117"></a>
### D-117 A batch answers each loan on its own; only a malformed batch is refused whole

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: the batch exists so that the replay does not take hours (D-008); conceptually it is many single requests together.
- **Decision**: `POST /predict/batch` answers 200 with one result per loan in the same order, each a prediction or its errors. Valid loans are scored and stored; invalid ones are recorded in `serving.requests`. Only a structural error refuses the whole batch with 422: not a list, empty, more than `API_MAX_BATCH` (1,000) loans, broken JSON.
- **Alternatives considered**: (A) all or nothing: simple and atomic, but one odd loan blocks the other 999 of its month; (C) 207 Multi-Status: as the decision, with a WebDAV status few clients expect.
- **Why**: each loan is independent, as in reality, and a batch gives exactly what the loans one by one give.
- **Consequences**: the client checks each item, not only the status. A batch of 1,000 takes about one second (T18.13). Test T18.4.

<a id="d-118"></a>
### D-118 API keys, one list per permission, several valid at once for rotation

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: everything runs in docker compose today, but the API will reach AWS (F7), and `/admin/reload` changes the model in use.
- **Decision**: a key in the header `X-API-Key`. Two lists of `name:key` pairs from environment secrets: `API_KEYS_PREDICT` (the replayer) and `API_KEYS_ADMIN` (the flow). Keys of at least 32 characters, compared in constant time against every configured key; no key or a wrong one gives 401, a key of the other permission 403. `/health` and `/health/live` are open. Logs and `serving.requests` record the name, never the key. Rotation without downtime: add the new key, move the clients, remove the old one; in AWS, Secrets Manager rotates it on a schedule.
- **Alternatives considered**: (A) no authentication, trusting the compose network: anyone reaching the port could predict or reload; (C) OAuth2 with JWT: the most complete, but an identity server for two machine clients.
- **Why**: the usual choice between internal services; it separates the permission to reload, and moves to Secrets Manager without changing the code.
- **Consequences**: `credit_risk/api/settings.py`; development keys in `.env.example`. Test T18.5.

<a id="d-119"></a>
### D-119 FastAPI and uvicorn in the main dependencies, at the version Prefect allows

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: one `uv.lock` for the project. Prefect requires FastAPI below 0.151 (D-103), so the lock has FastAPI 0.150.0 (19 October 2026).
- **Decision**: FastAPI and uvicorn in the main dependencies (the `serve` image), at the version the lock allows. Also `psycopg[pool]` for the connection pool, and `httpx` in the `dev` group for the test client.
- **Alternatives considered**: (B) two locks, one for the API: FastAPI free of the cap, but scikit-learn or LightGBM could differ between training and serving, and a model saved with one version may predict differently or not load with another; (C) Prefect in an image and lock of its own: its worker runs training, so it needs the same libraries; it ends up as (B).
- **Why**: serving with exactly the libraries of training is worth more than the latest FastAPI; pip-audit and Dependabot watch for vulnerabilities, and an unfixed one in 0.150 reopens this decision.
- **Consequences**: the `serve` image grows a few MB (B5 keeps its 800 MB budget).

<a id="d-120"></a>
### D-120 The buy rule is registered in MLflow like a model, and chosen again when the champion pair changes

Date: 2026-11-24 · Step: 5.1 (consequence of D-112) · Status: Active

- **Context**: the minimum of the buy rule is chosen on validation with one pair of models (D-084, D-096); until now only the business report of F3 computed it. PD and LGD are promoted apart, so a change of either invalidates it.
- **Decision**: a registered "model" `buy_rule` with its own alias `champion`: a small object with the minimum, the PD and LGD versions it was chosen with and the training set version, logged as a run with every required field (D-079; metric: realised net return on validation at that minimum, with its bootstrap interval). A flow task `buy-rule` chooses it again whenever the champion PD or LGD changed (a pair that already has a rule reuses it, D-101) and records a `promoted` alert. The API serves the threshold only when the rule matches the pair it uses; otherwise "threshold not available", with the risk still served.
- **Alternatives considered**: (B) a tag on the PD version: nothing new, but it goes stale when only the LGD changes; (C) a fixed value in the configuration: it does not follow the models and contradicts D-084.
- **Why**: the rule is a versioned artefact like the models; for each prediction we know which rule decided it.
- **Consequences**: `credit_risk/buy_rule.py`; the flow has six tasks (`buy-rule` and `reload` after the LGD). A manual rollback leaves the threshold unavailable until the next retraining. Tests T18.10 and T19.1.

<a id="d-121"></a>
### D-121 A prediction is written before it is answered, in the same transaction

Date: 2026-11-24 · Step: 5.1 · Status: Active

- **Context**: D-008 says every prediction is stored. The write costs a few milliseconds.
- **Decision**: the API scores, writes the request and its predictions in one transaction, commits, and only then answers. If the database fails, 503 and no prediction. A batch is one transaction.
- **Alternatives considered**: (B) writing in the background after answering: slightly faster, and the API answers with the database down, but a crash loses predictions already given; (C) an external queue (Kafka, SQS) and a consumer: what very high volumes use, but one more service to run for our volume.
- **Why**: in credit, being able to prove what was predicted is worth more than a few milliseconds, and the latency stays far within the objective (T18.13).
- **Consequences**: the API is not ready while the database is down (`/health`). Test T18.7.

<a id="d-122"></a>
### D-122 Latency is measured under an open load of 20 requests a second; capacity is measured apart

Date: 2026-11-24 · Step: 5.1 (changes T18.13) · Status: Active

- **Context**: T18.13 as approved sent requests from 20 clients without pause for 60 seconds. One process of the API answers about 70 requests a second (about 14 ms of work each), so with 20 requests always queued each waits for the other 19: p95 364 ms. That measures saturation, not latency.
- **Decision**: T18.13 sends 20 requests a second at a fixed rate for 60 seconds (an open load, as listings arrive) and requires p95 below 200 ms. The capacity, answers a second with 20 clients that never pause, is measured after it and recorded, without a threshold.
- **Alternatives considered**: (B) keep 20 clients and run several API containers behind a load balancer (nginx): the original test passes and horizontal scaling shows, but more infrastructure now, and real scaling is decided in AWS (F7); (C) keep it and optimise further: one process would need under about 9 ms a request, with no guarantee.
- **Why**: the standard split of a load test: latency at a given load under capacity, capacity apart. 20 a second is more than a thousand times Lending Club's peak (about 40,000 listings a month in 2018, less than one a minute).
- **Consequences**: measured here: p95 30 ms at 20 a second; capacity 70 answers a second for one process; a batch of 1,000 in about one second (E-044, E-045).

<a id="d-123"></a>
### D-123 The replayer is the simulated investor: a step of `advance`, after publishing a month and before the system's flow

Date: 2026-11-25 · Step: 4.2, moved to F5 by D-098 · Status: Active

- **Context**: D-098 replaced the batch prediction flow of step 4.2 by a replayer that sends each month to the API (D-008). In reality the caller of the API is the investor, outside the system. A loan listed in month M must be decided by the champions that existed when it was listed, trained up to M-1, as T18.15 did.
- **Decision**: the replayer is part of the simulated world (D-043), in `credit_risk.simulator.replayer`. `advance` publishes month M, then the investor sends M's listings to the API and buys, then the system's monthly flow runs (load, and in the cadence months, retraining). A month the investor completed is recorded in `sim.invested` and is not sent again when the clock repeats it after a failure of the system's flow: the investor already acted.
- **Alternatives considered**: (B) the simulated world, after the system's flow: in January, April, July and October the new champion would score loans listed before it existed, a timing error; (C) a task of the system's flow: the simplest, but the system would call itself in batch, which is the old 4.2 that D-098 replaced, and it mixes the investor with the system.
- **Why**: each month is decided with the models of its moment, and the system stays apart from its client.
- **Consequences**: `advance` needs the API up (in compose, `clock` depends on `api`). Tests T21.2, T21.3.

<a id="d-124"></a>
### D-124 The investor reports what it bought to the API (`POST /purchases`, `serving.purchases`)

Date: 2026-11-25 · Step: 4.2 (in F5) · Status: Active

- **Context**: the investor applies the monthly cap of D-085 (D-112). F6 will watch the realised return of what was bought, and the system never reads `sim` (T17.3). The first recommendation was to keep the purchases in `sim` and let F6 recompute what the rule would buy from `serving.predictions`; Juan pointed out that this measures the policy, not the real orders.
- **Decision**: the investor reports its purchases to the API, `POST /purchases` with its predict key, and they are stored in `serving.purchases`. F6 measures on these.
- **Alternatives considered**: (A) only in `sim.purchases`, recomputed by F6: the system does not depend on its client, but it sees the policy, not the orders; in reality they part (a loan filled by others, a purchase skipped by hand, a failed order, no cash) and F6 would measure a portfolio that does not exist; (C) not stored: nothing to check.
- **Why**: logging the actions taken, not only the predictions, is how a system that decides is monitored. In our simulation both lists are equal because the replayer follows the rule exactly; the design is the one production needs.
- **Consequences**: one more endpoint, table and tests (T20). D-126, D-128 and D-129 settle what a purchase carries.

<a id="d-125"></a>
### D-125 The investor retries an API that does not answer, then stops the clock; a refused listing is not bought and is counted

Date: 2026-11-25 · Step: 4.2 (in F5) · Status: Active

- **Context**: two failures differ: the API or its database not answering (passing), and one listing refused with 422 inside a batch (a data problem; it should not happen with real data, cleaned as by the monthly load).
- **Decision**: no connection, a timeout or a 5xx answer is retried three times, after 10, 30 and 90 seconds, as D-102; then `advance` fails, the clock does not move and the month is repeated later. A refused listing is not bought, stays in `serving.requests` (D-115) and is counted in the month's summary, and the month goes on. A refused purchase stops the month: it would be a bug.
- **Alternatives considered**: (B) no retries: simpler, but a one-second cut repeats the month; (C) go on: what fails is not bought and the month counts as done, losing purchases with no warning.
- **Why**: it survives short cuts, never loses or duplicates a month (D-114, D-129), and one bad listing does not stop the clock.
- **Consequences**: a long outage of the API stops the clock, which is what we want to see. Test T21.4.

<a id="d-126"></a>
### D-126 Every answer carries a `prediction_id`; a purchase names only that id; exceptions to the rule are recorded, not refused

Date: 2026-11-25 · Step: 4.2 (in F5) · Status: Active

- **Context**: to attribute each dollar to the models behind it, a purchase must point to the answer it was decided on; a loan can have several predictions, one per pair of models (D-114). A first proposal had the client send the versions of PD and LGD; Juan refused it: a client should know nothing of models.
- **Decision**: every answer of `/predict` and `/predict/batch` carries its `prediction_id`. To buy, the investor sends that id, like the number of a quote. An unknown id refuses that purchase (422). A purchase that does not pass the threshold, has no threshold or is of an uncovered term is accepted and marked (`policy`: `passes`, `below_minimum`, `no_threshold`, `not_covered`).
- **Alternatives considered**: (B) only the loan id, linked to the last prediction before the purchase: if the investor decided on an earlier answer, F6 would credit the wrong model; (C) no checks: purchases of loans never scored.
- **Why**: the simplest client and an exact link to the model; exceptions are what F6 must see.
- **Consequences**: one more field in every answer. Tests T20.1, T20.3, T20.4.

<a id="d-127"></a>
### D-127 The investor starts the month after T0

Date: 2026-11-25 · Step: 4.2 (in F5) · Status: Active

- **Context**: the first `advance` publishes the history up to T0 (2014-01) and the flow trains the first champions there. Before that there is no model.
- **Decision**: a fixed rule: the investor sends nothing for the history or T0 itself, and starts the month after (2014-02).
- **Alternatives considered**: (B) start when the API has a champion, asking `/health`: if a champion vanished by a bug in 2016, the investor would stop buying with nobody noticing; (C) send the history too: models would score the loans they were trained on, a leak that would fill `serving.predictions` with false results for F6.
- **Why**: it is what happens in reality (one invests once the model exists) and matches T18.15. An API with no model in a later month is an error that stops `advance` (D-125), never read as "no model yet".
- **Consequences**: test T21.2.

<a id="d-128"></a>
### D-128 A purchase carries its amount, in notes of 25 dollars, up to the loan's amount

Date: 2026-11-25 · Step: 4.2 (in F5) · Status: Active

- **Context**: Lending Club sold notes of 25 dollars, several of the same loan if wanted. Our investor buys one note per loan (D-085). F6 needs the money behind each purchase.
- **Decision**: a purchase carries `amount`, a positive multiple of 25 that, with what the client already holds of that loan, does not exceed the loan's amount. The replayer always sends 25.
- **Alternatives considered**: (B) no amount, always 25: simpler, but the API would assume the investor's strategy.
- **Why**: as the platform works; F6 weighs each purchase by its money; a change of strategy (more notes on safer loans, if the buy rule of D-097 is revisited) changes only the replayer.
- **Consequences**: an amount check (T20.3). The 25 is the strategy of D-085, under which the minimum of D-084 and the comparison of D-097 were measured.

<a id="d-129"></a>
### D-129 The client's own order number makes a repeated purchase harmless and allows repurchases

Date: 2026-11-25 · Step: 4.2 (in F5) · Status: Active

- **Context**: a month repeated after a failure (D-125) must not buy twice. A first proposal made a purchase unique per loan, then per client and loan; Juan pointed out that this forbids an investor to add to its share later, an unwanted restriction.
- **Decision**: every purchase carries the client's own order number (`order_id`, an idempotency key, as payment APIs use). The same order again returns the stored purchase (`stored_earlier`); the same number with another content is a conflict (409); a new order on the same loan adds to the share (a repurchase), up to the loan's amount. Unique (client, order number) in the database; the replayer's numbers are the month and the loan, so repeating a month gives the same numbers.
- **Alternatives considered**: (B) one purchase per client and loan: no repurchases; (C) no control, everything adds: repeating a month would duplicate purchases.
- **Why**: the standard pattern: repurchases allowed and a repeated request harmless.
- **Consequences**: the request is answered with 200 and a status per purchase (`created`, `stored_earlier`, `refused` with 409 or 422), as a batch (D-117). Each request locks the client's order and its share of the loan until it commits, so two at once cannot both create an order or overfill a loan. Tests T20.2, T20.5.

