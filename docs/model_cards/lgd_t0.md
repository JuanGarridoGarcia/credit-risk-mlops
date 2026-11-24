# Model card: lgd version 2

## Model

- Model: baseline
- Target: LGD
- Cutoff: 2014-01
- Training set version: `a85eab63f58fe0372137a1afb37f7de779558825d07066bf9f56fc9645005819`
- Commit: `53b9938ff0f72d568b23ddfb35271c36f1151e7b-dirty`
- Seed: 2014
- Run: `a88fb0f198cf426a8e4ca363e01a4532`
- Terms covered: 36 months (D-070)
- Level shift fitted on validation (D-094): 0.050415

## Intended use

Estimate the share of the amount lent that is lost when a Lending Club loan defaults (D-017), for the expected return of the buy rule (D-084).

## Uses not intended

- Deciding whether a person gets credit: the model ranks notes for an investor, it was never built or validated as a lending decision.
- Loans of a term it does not cover (D-070): they get no prediction.
- Loans listed long after its cutoff without a newer training: the data drift (the LGD rose every year up to 2010, D-094).
- Any other lender or population: it learned Lending Club's listings only.

## Data

| Split | Loans | Defaults |
|---|---|---|
| train | 992 | 992 |
| validation | 344 | 344 |

## Performance

On validation, with 95% bootstrap intervals (D-075).

| Metric | Value | Low | High |
|---|---|---|---|
| calibration_error | 0.0000 | 0.0000 | 0.0263 |
| rmse | 0.2156 | 0.2015 | 0.2296 |

## Segments

Not judged: this version is the reference the first challenger was compared with (D-090).

## Behavioural battery

Not applicable: the battery checks the PD (D-086).

## Most important features

Mean absolute contribution on validation, in LGD (D-083).

| Feature | Mean absolute contribution |
|---|---|
| grade | 0.0160 |

## Features left out on purpose

- State and zip code: they can stand in for protected characteristics such as race (D-018); a credit model that uses them risks unfair treatment of whole areas.
- Free text (employment title, description): not reliable, and can carry personal information (D-015).
- `installment`: it is computed from the amount funded, known only after listing (leak, decided in F3).
- Payment and outcome columns: they are known only after the loan is listed (D-014).
- Identifiers: they carry no information about risk.

## Known limits

- Trained on the loans known at its cutoff only; validation is the last six matured months of each term (D-069), so the newest loans it scores are a year or more younger.
- Built on a simulation of Lending Club's history replayed month by month (D-008); the real platform closed its note programme in 2020.
- Calibrated on validation (Platt for the PD, D-076; a level shift for the LGD, D-094); a trend after validation is not in the model and is watched by monitoring (F6).
- Reasons are contributions to the model's log-odds, not causes.
- Ranking better than the grade baseline does not by itself earn more: at T0 the buy rule with these models earned less than with the baseline at caps of 10% and 20% (D-097).
