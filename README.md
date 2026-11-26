# credit-risk-mlops

[![CI](https://github.com/JuanGarridoGarcia/credit-risk-mlops/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JuanGarridoGarcia/credit-risk-mlops/actions/workflows/ci.yml)

Production system (MLOps) for a Lending Club credit risk model: for every loan listed on the platform it serves the probability of default (PD), the loss given default (LGD) and the expected loss (EL) through an API, stores every prediction, and monitors and retrains the models over a simulated 2014 to 2018 timeline.

## Authorship

Designed by **Juan Garrido García**: every design decision in this repository was taken by him after debating the alternatives (see the [decision log](docs/decisions.md)), and every test was approved by him before it was written. Implemented with AI agents.

## The problem

An investor on Lending Club decides, every time a loan is listed, whether to buy it, and holds it until it ends. Lending Club already shows a grade (A1 to G5) and an interest rate. The question this system answers: **does a model know more than the grade the investor already sees for free, enough to lose less money with the same budget?** Full definition in [`docs/problem.md`](docs/problem.md).

## Architecture

Target architecture; the parts already built are marked.

```
   simulated month of listings
             |
             v
   replayer -----> API (PD, LGD, EL + explanation) -----> Postgres [built]
   (investor,       [built]                                (loans, predictions,
    buys) [built]   ^                                       purchases, labels,
                    |                                       metrics)
            model registry <---- training flow                  |
              (MLflow)  [built]   (Prefect) [built]              v
                    ^                  ^                   monitoring job
                    |                  |                  (drift, early warning,
                    +---- retraining decision <------------ performance, fairness)
                                                                 |
                                                                 v
                                                             dashboard

   Underneath, from day one [built]: one Python package, pinned environment,
   Docker image, docker compose, CI on every pull request, weekly security scans;
   since F5, every merge publishes the tested images to GHCR (continuous delivery).
```

## Results

First training, at T0 = January 2014 (36-month loans; validation: 4,324 loans, 429 defaults). Every model was judged against a grade-only baseline under the same promotion rules.

| Model | Validation result | Outcome |
|---|---|---|
| Probability of default | AUC 0.677 for the logistic regression against 0.636 for the baseline; LightGBM (0.680) is not better by more than the noise, so the simpler model wins ([D-068](docs/decisions.md#d-068)) | Logistic regression promoted |
| Loss given default | No candidate beats the mean by grade (RMSE 0.216); every model was 5 points too low because losses rise year after year, so the level is now set on the most recent period ([D-094](docs/decisions.md#d-094)) | Baseline stays |

Business result: an investor using the T0 models for the next 12 months (loans listed from February 2014 to January 2015, final outcomes, same budget each month) did not earn more than one using the grade alone.

| Cap (share of last month's loans) | Our models | Grade baseline |
|---|---|---|
| 5% | +8.99% | +8.95% |
| 10% | +8.46% | +8.95% |
| 20% | +7.49% | +8.70% |

Our investor is more selective, so more money stays idle, and the notes it buys do not default less. Better ranking did not become better choices under this buy rule; the result is reported as measured and the rule will be reviewed in a later step ([D-097](docs/decisions.md#d-097)). Details in the [technical document](docs/technical.md#5-f3-model).

## Key decisions

One line per theme; each links to its full card with the alternatives considered.

| Theme | Decision |
|---|---|
| Framing | The user is an investor deciding at listing time ([D-001](docs/decisions.md#d-001)); the PD target is default at any point of the loan's life, with the 12-month rate as early warning ([D-003](docs/decisions.md#d-003)) |
| No leakage | A column is a feature only if it is proven visible to the investor at listing ([D-014](docs/decisions.md#d-014)); fields reported only from a given year enter at a retraining, never as "missing" ([D-016](docs/decisions.md#d-016)) |
| Fairness | State and zip code are not features (proxies for protected attributes); the state is kept only to monitor fairness ([D-018](docs/decisions.md#d-018)) |
| Architecture | A single prediction path, the API, with every prediction stored ([D-008](docs/decisions.md#d-008)) |
| Engineering | Three families of tests (code now; data from F2, model from F3), each approved before it is written and listed in the [test catalogue](docs/tests.md) ([D-057](docs/decisions.md#d-057)); CI is the only way into `main`, with no exceptions ([D-028](docs/decisions.md#d-028), [D-032](docs/decisions.md#d-032)); everything from outside is pinned by its fingerprint ([D-030](docs/decisions.md#d-030)) |
| Orchestration | Prefect runs the monthly cycle: load and validate, version, train PD and LGD, promote; only identifiers travel between tasks ([D-099](docs/decisions.md#d-099), [D-100](docs/decisions.md#d-100)); running a month again changes nothing ([D-101](docs/decisions.md#d-101)); only transient failures are retried ([D-102](docs/decisions.md#d-102)); the simulator stays outside the system ([D-105](docs/decisions.md#d-105)); retraining every quarter ([D-106](docs/decisions.md#d-106)); a simulated clock moves the system one month at a time and never skips or repeats a month ([D-107](docs/decisions.md#d-107)); failures, promotions, rejections and rollbacks recorded as alerts ([D-108](docs/decisions.md#d-108)) |
| Serving | One API, the only way to a prediction ([D-008](docs/decisions.md#d-008)): it takes listings as the provider delivers them and cleans them with the code of the monthly load ([D-116](docs/decisions.md#d-116)); it answers PD, LGD, expected loss, expected return and whether the loan passes the buy threshold, with four reasons and the versions used ([D-112](docs/decisions.md#d-112)); every answer is stored before it leaves, once per loan and pair of models ([D-113](docs/decisions.md#d-113), [D-114](docs/decisions.md#d-114), [D-121](docs/decisions.md#d-121)); champions come from the MLflow registry and are swapped as a whole after a notice from the flow ([D-110](docs/decisions.md#d-110), [D-111](docs/decisions.md#d-111)); API keys per permission ([D-118](docs/decisions.md#d-118)); a simulated investor sends each month to the API before the system's flow and reports what it bought, so monitoring measures real orders ([D-123](docs/decisions.md#d-123), [D-124](docs/decisions.md#d-124)), each tied to the answer it was decided on and made harmless to repeat by its order number ([D-126](docs/decisions.md#d-126), [D-129](docs/decisions.md#d-129)) |
| Delivery | Every merge to main publishes the serve and train images that CI tested, without building them again, to GitHub Container Registry ([D-130](docs/decisions.md#d-130), [D-131](docs/decisions.md#d-131), [D-133](docs/decisions.md#d-133)); each is named by its commit for ever, and `main` moves to it only after Trivy finds nothing serious and a smoke test gets a real prediction from the published images ([D-132](docs/decisions.md#d-132), [D-134](docs/decisions.md#d-134), [D-135](docs/decisions.md#d-135)); a release tag `vX.Y.Z` adds the version to what main published ([D-132](docs/decisions.md#d-132)) |
| Monitoring | Every month the flow measures what the models received and answered against the 12 months before their cutoff, with the PSI ([D-138](docs/decisions.md#d-138), [D-139](docs/decisions.md#d-139), [D-141](docs/decisions.md#d-141)); labels come 3 to 5 years late, so a 12-month default rate checks the PD after 17 months ([D-143](docs/decisions.md#d-143)) and matured cohorts are measured like a challenger ([D-144](docs/decisions.md#d-144)) |
| Modelling | Baselines use only the grade ([D-004](docs/decisions.md#d-004)); models are judged on ranking and calibration ([D-006](docs/decisions.md#d-006)) and on realised return at equal budget ([D-007](docs/decisions.md#d-007)). Training decisions come in F3 |

## How to run it

Requirements: [uv](https://docs.astral.sh/uv/), Docker with docker compose, and `make`. On Windows, use WSL2.

```bash
git clone https://github.com/JuanGarridoGarcia/credit-risk-mlops.git
cd credit-risk-mlops
make install            # environment from uv.lock, git hooks, .env from .env.example
make lint               # style, formatting, types, lock in sync
make test               # unit tests with coverage
make build              # the two application images, serve and train
make up                 # Postgres, MLflow (UI at http://localhost:5000), Prefect (UI at http://localhost:4200), its worker, the simulated clock and the API (http://localhost:8000/docs)
make test-integration   # tests against Postgres, MLflow and the images
make train T=2014-01    # train, register and try to promote the PD and LGD models
make advance            # simulated clock: publish the next month and run the monthly flow for it
make replay TO=2014-12  # advance month by month until December 2014
make rollback MODEL=pd  # put back the previous champion
make down               # stop; data stays in the volume
```

Instead of `make build`, the stack can start from a published version (any commit of main: `:sha-abc1234`; the latest good one: `:main`):

```bash
docker pull ghcr.io/juangarridogarcia/credit-risk-serve:main
docker pull ghcr.io/juangarridogarcia/credit-risk-train:main
SERVE_IMAGE=ghcr.io/juangarridogarcia/credit-risk-serve:main \
TRAIN_IMAGE=ghcr.io/juangarridogarcia/credit-risk-train:main make up
```

`make help` lists every command; `make check` runs everything the CI runs. The data audit notebook needs a Kaggle token: see [`notebooks/00_data_audit.ipynb`](notebooks/00_data_audit.ipynb).

## Status

| Phase | Content | Status |
|---|---|---|
| F0 Framing | Problem, metrics, baselines, data audit | Done |
| F1 Foundations | Environment, code quality, Docker, CI, documentation | Done |
| F2 Data | Ingestion, validation, versioning, features | Done |
| F3 Model | Baselines, experiments, model tests, registry, explainability | Done |
| F4 Automation | Orchestrated monthly cycle and simulated clock | Done |
| F5 Deployment | API, replayer, published image, continuous delivery | Done (API in #12; simulated investor and purchases in #13; published images in #14, first publication after the fixes of #15 to #17) |
| F6 Monitoring | Drift, dashboard, alerts, triggered retraining | In progress (drift, early warning and real performance every month in this pull request; dashboards and alerts next) |
| F7 Closing | End to end, AWS with infrastructure as code | Pending |

Step by step detail in the [tracking sheet](docs/technical.md#1-tracking-sheet).

## Repository map

| Path | Contents |
|---|---|
| `src/credit_risk/` | The system, as an installable Python package |
| `tests/` | `unit/` (no services) and `integration/` (Docker) |
| `docs/` | [Problem](docs/problem.md), [data audit](docs/data_audit.md), [decisions](docs/decisions.md), [errors](docs/errors.md), [validation rules](docs/validation_rules.md), [test catalogue](docs/tests.md), [technical document](docs/technical.md) |
| `notebooks/` | Exploration and report notebooks (never production code) |
| `reports/` | Tables and figures generated by the notebooks |

The research phase of this work, which answers "which model and why", lives in [A Deep Dive into Expected Loss](https://github.com/JuanGarridoGarcia/A-Deep-Dive-into-Expected-Loss-through-Credit-Scoring-Industry-Standard-Machine-Learning). This repository answers "how that model is operated in production".
