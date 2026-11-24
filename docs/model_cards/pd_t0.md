# Model card: pd version 1

## Model

- Model: logistic
- Target: PD
- Cutoff: 2014-01
- Training set version: `a85eab63f58fe0372137a1afb37f7de779558825d07066bf9f56fc9645005819`
- Commit: `53b9938ff0f72d568b23ddfb35271c36f1151e7b-dirty`
- Seed: 2014
- Run: `40e91abe292848868ddb22f4f7455f35`
- Terms covered: 36 months (D-070)
- Features removed for a wrong sign (D-092): pub_rec,credit_history_months
- Platt scaling (a, b) on validation (D-076): [1.0331033173424395, -0.12578447203811535]

## Intended use

Estimate the probability that a Lending Club loan listed now defaults before the end of its term, for an investor who decides which notes to buy (D-001). It is used with the LGD in the buy rule (D-084), and served with its four main reasons (D-083).

## Uses not intended

- Deciding whether a person gets credit: the model ranks notes for an investor, it was never built or validated as a lending decision.
- Loans of a term it does not cover (D-070): they get no prediction.
- Loans listed long after its cutoff without a newer training: the data drift (the LGD rose every year up to 2010, D-094).
- Any other lender or population: it learned Lending Club's listings only.

## Data

| Split | Loans | Defaults |
|---|---|---|
| train | 7733 | 1019 |
| validation | 4324 | 429 |

## Performance

On validation, with 95% bootstrap intervals (D-075).

| Metric | Value | Low | High |
|---|---|---|---|
| auc | 0.6773 | 0.6516 | 0.7020 |
| brier | 0.0855 | 0.0842 | 0.0867 |

Against the champion it was judged with: auc 0.6773 against 0.6357, improvement interval [0.0206, 0.0617]. Outcome: promoted; reasons: none.

## Segments

| Segment | Metric | New | Current | Low | High | Margin | Blocking |
|---|---|---|---|---|---|---|---|
| grade A+B | auc | 0.6663 | 0.6025 | 0.0300 | 0.0971 | 0.01 | False |
| grade A+B | calibration_error | 0.0009 | 0.0019 | -0.0001 | 0.0020 | 0.01 | False |
| grade C | auc | 0.6342 | 0.5000 | 0.0795 | 0.1867 | 0.01 | False |
| grade C | calibration_error | 0.0072 | 0.0058 | -0.0044 | 0.0014 | 0.01 | False |
| grade D+E+F+G | auc | 0.5916 | 0.5238 | 0.0069 | 0.1247 | 0.01 | False |
| grade D+E+F+G | calibration_error | 0.0066 | 0.0011 | -0.0097 | -0.0012 | 0.01 | False |
| term 36 months | auc | 0.6773 | 0.6357 | 0.0206 | 0.0617 | 0.01 | False |
| term 36 months | calibration_error | 0.0000 | 0.0000 | -0.0013 | 0.0008 | 0.01 | False |
| quarter 2010Q1 | auc | 0.6626 | 0.6016 | 0.0179 | 0.1027 | 0.01 | False |
| quarter 2010Q1 | calibration_error | 0.0135 | 0.0093 | -0.0069 | -0.0013 | 0.01 | False |
| quarter 2010Q2 | auc | 0.6865 | 0.6361 | 0.0227 | 0.0785 | 0.01 | False |
| quarter 2010Q2 | calibration_error | 0.0051 | 0.0072 | 0.0003 | 0.0040 | 0.01 | False |
| quarter 2010Q3 | auc | 0.6648 | 0.6504 | -0.0245 | 0.0474 | 0.01 | False |
| quarter 2010Q3 | calibration_error | 0.0009 | 0.0063 | 0.0022 | 0.0070 | 0.01 | False |

## Behavioural battery

| Check | Passed |
|---|---|
| invariance: unused fields | True |
| invariance: alone or in a batch | True |
| direction: int_rate | True |
| direction: dti | True |
| direction: revol_util | True |
| direction: inq_last_6mths | True |
| direction: delinq_2yrs | True |
| direction: pub_rec | True |
| direction: fico | True |
| direction: annual_inc | True |
| direction: credit_history_months | True |
| minimum: good profile below bad profile | True |
| minimum: every PD in [0, 1] | True |
| minimum: empty optional fields are scored | True |
| minimum: an uncovered term gets no PD | True |
| time: p95 under 50 ms | True |

## Most important features

Mean absolute contribution on validation, in log-odds (D-083).

| Feature | Mean absolute contribution |
|---|---|
| grade | 0.2055 |
| purpose | 0.1939 |
| inq_last_6mths | 0.1366 |
| loan_amnt | 0.1306 |
| annual_inc | 0.1247 |
| sub_grade | 0.1164 |
| fico | 0.1160 |
| verification_status | 0.1091 |
| mths_since_last_delinq | 0.0948 |
| int_rate | 0.0892 |
| mths_since_last_record | 0.0819 |
| revol_bal | 0.0468 |
| emp_length | 0.0375 |
| revol_util | 0.0362 |
| open_acc | 0.0186 |
| home_ownership | 0.0126 |
| delinq_2yrs | 0.0059 |
| total_acc | 0.0035 |
| tax_liens | 0.0027 |
| dti | 0.0026 |
| collections_12_mths_ex_med | 0.0005 |
| chargeoff_within_12_mths | 0.0005 |

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
