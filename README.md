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
                    ^                                      (loans, predictions,
                    |                                       labels, metrics)
            model registry <---- training flow                  |
              (MLflow)            (orchestrated)                 v
                    ^                  ^                   monitoring job
                    |                  |                  (drift, early warning,
                    +---- retraining decision <------------ performance, fairness)
                                                                 |
                                                                 v
                                                             dashboard

   Underneath, from day one [built]: one Python package, pinned environment,
   Docker image, docker compose, CI on every pull request, weekly security scans.
```

## Results

First training, at T0 = January 2014 (36-month loans; validation: 4,324 loans, 429 defaults). Every model was judged against a grade-only baseline under the same promotion rules.

| Model | Validation result | Outcome |
|---|---|---|
| Probability of default | AUC 0.677 for the logistic regression against 0.636 for the baseline; LightGBM (0.680) is not better by more than the noise, so the simpler model wins ([D-068](docs/decisions.md#d-068)) | Logistic regression promoted |
| Loss given default | No candidate beats the mean by grade (RMSE 0.216); every model was 5 points too low because losses rise year after year, so the level is now set on the most recent period ([D-094](docs/decisions.md#d-094)) | Baseline stays |

The business result (realised return of the buy rule) comes with the third part of F3. Details in the [technical document](docs/technical.md#5-f3-model).

## Key decisions

One line per theme; each links to its full card with the alternatives considered.

| Theme | Decision |
|---|---|
| Framing | The user is an investor deciding at listing time ([D-001](docs/decisions.md#d-001)); the PD target is default at any point of the loan's life, with the 12-month rate as early warning ([D-003](docs/decisions.md#d-003)) |
| No leakage | A column is a feature only if it is proven visible to the investor at listing ([D-014](docs/decisions.md#d-014)); fields reported only from a given year enter at a retraining, never as "missing" ([D-016](docs/decisions.md#d-016)) |
| Fairness | State and zip code are not features (proxies for protected attributes); the state is kept only to monitor fairness ([D-018](docs/decisions.md#d-018)) |
| Architecture | A single prediction path, the API, with every prediction stored ([D-008](docs/decisions.md#d-008)) |
| Engineering | Three families of tests (code now; data from F2, model from F3), each approved before it is written and listed in the [test catalogue](docs/tests.md) ([D-057](docs/decisions.md#d-057)); CI is the only way into `main`, with no exceptions ([D-028](docs/decisions.md#d-028), [D-032](docs/decisions.md#d-032)); everything from outside is pinned by its fingerprint ([D-030](docs/decisions.md#d-030)) |
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
make up                 # Postgres and MLflow (UI at http://localhost:5000), waits until healthy
make test-integration   # tests against Postgres, MLflow and the images
make train T=2014-01    # train, register and try to promote the PD and LGD models
make rollback MODEL=pd  # put back the previous champion
make down               # stop; data stays in the volume
```

`make help` lists every command; `make check` runs everything the CI runs. The data audit notebook needs a Kaggle token: see [`notebooks/00_data_audit.ipynb`](notebooks/00_data_audit.ipynb).

## Status

| Phase | Content | Status |
|---|---|---|
| F0 Framing | Problem, metrics, baselines, data audit | Done |
| F1 Foundations | Environment, code quality, Docker, CI, documentation | Done |
| F2 Data | Ingestion, validation, versioning, features | Done |
| F3 Model | Baselines, experiments, model tests, registry, explainability | In progress (data merged; training in review; explainability and business next) |
| F4 Automation | Orchestrated training | Pending |
| F5 Deployment | API, published image, continuous delivery | Pending |
| F6 Monitoring | Drift, dashboard, alerts, triggered retraining | Pending |
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
