# Problem definition

Step 0.1 of the playbook. Status: **approved by Juan on 2026-11-20**. Every decision below was taken by Juan on 2026-11-20 unless marked as a proposal.

## 1. Business context

Lending Club was a US peer-to-peer lending marketplace (2007 to 2020). Borrowers applied for unsecured consumer loans; Lending Club screened them, assigned a grade (A1 to G5) and an interest rate, and **listed** the approved loans on its platform. Investors then chose which listed loans to fund.

This project takes the point of view of **an investor who, every time a loan is listed, decides whether to buy it**. The investor has a limited budget and holds every loan bought until it ends (repaid, prepaid or charged off).

The research phase of this work lives in a separate repository ([A Deep Dive into Expected Loss](https://github.com/JuanGarridoGarcia/A-Deep-Dive-into-Expected-Loss-through-Credit-Scoring-Industry-Standard-Machine-Learning)). It answers "which model and why". This repository answers "how that model is operated in production".

## 2. The decision

```
   loan listed  --->  score: PD, LGD, EL  --->  buy rule  --->  buy / do not buy
   (application       (at listing time,          (decided in
    data only)         nothing from the future)   step 3.x)
```

Decided: the exact buy rule (for example, a threshold on expected loss rate, or on expected return net of expected loss) is **left open until F3**, because it needs the trained models and their noise to be set sensibly. What is fixed now is how the rule will be judged (section 5).

## 3. What is predicted

One prediction per loan, at listing time, using only information available at that moment.

| Output | Definition | Notes |
|---|---|---|
| PD | Probability that the loan defaults **at any point during its life** | Lifetime horizon, because the investor holds the loan to the end. The Basel 12-month horizon serves a different purpose (a bank's annual capital) |
| LGD | Share of the funded amount lost if the loan defaults: `(EAD - principal repaid - recoveries) / EAD` | Same target as the research phase |
| EAD | Funded amount at origination | Known at listing |
| EL | `PD x LGD x EAD`, lifetime expected loss in dollars; EL rate = `EL / EAD` | Derived, not a separate model |

A loan counts as **defaulted** when its final status is charged off or default. The exact status mapping, and how "does not meet the credit policy" loans are treated, is fixed in step 0.2.

## 4. How predictions are served (decision B)

There is **a single prediction path: the API**.

| Component | What it does | When |
|---|---|---|
| API | Scores one loan, or a small batch of loans, at listing. Every prediction is stored with the model version and its inputs | Every time a loan is listed |
| Replayer (simulation only) | Sends each month's historical loans to the API, in listing order, as if they arrived from Lending Club | Month by month, 2007 to 2018 |
| Monthly job | Reads the stored predictions and the labels that have arrived. Measures data drift, the early-warning default rate and, where labels are complete, real model performance. Decides whether to retrain | Once per simulated month |
| Portfolio re-scoring | Recomputes the EL of the portfolio already bought | Only when a new model becomes champion |

Why: the investor decides at the moment of listing, not at month end, so the realistic system scores one loan at a time. One path also removes the risk of two scoring implementations disagreeing. The cost is a batch endpoint, so that replaying about two million loans does not take hours.

## 5. Metrics

### 5.1 Model metrics

| Model | Metric | What it answers |
|---|---|---|
| PD | AUC | Does it rank loans from riskier to safer? |
| PD | Gini (`2 x AUC - 1`) | Same as AUC, in the form credit risk teams report it |
| PD | PR-AUC (area under the precision-recall curve) | Complementary. Sensitive to the minority class (defaults), unlike AUC |
| PD | Brier score and calibration by segment (term, grade, vintage) | Does a PD of 0.20 mean 2 defaults in 10? Needed because EL multiplies the PD |
| LGD | RMSE, MAE; mean predicted vs observed by segment | Is the loss level right where it matters? |
| EL | EL / realised loss, overall and by segment | Does the expected loss match what actually happened? |

Threshold metrics (confusion matrix, recall, precision) are **not** model metrics here, because the model outputs a probability and does not decide. They are reported in F3 at the threshold of the chosen buy rule, to show how many defaulters slip through and how many good payers are turned down.

### 5.2 Business metric

With the **same budget**, compare the portfolio bought by our rule with the portfolio bought by the baseline rule:

- realised default rate,
- realised loss (dollars and as a share of the amount invested),
- realised net return (payments received minus amount invested), which is what an investor ultimately cares about. Step 0.2 confirms that the data supports it.

Measured only on loans whose outcome is complete.

## 6. Baseline

The minimum a model must beat to be worth deploying.

| Model | Baseline | Status |
|---|---|---|
| PD | Logistic regression on Lending Club's `grade` only | Decided. It answers: does the model know more than the grade the investor already sees for free? |
| LGD | Mean LGD of the defaulted training loans **of each grade** | Decided. Same question as for the PD: does the model know more than the grade? Step 3.1 also reports the constant (global mean) as a reference; in the research phase the constant gave RMSE 23.4 against 22.6 for the best model |
| EL | Baseline PD x baseline LGD x EAD | Follows from the two above: what an investor can compute from the grade alone |

**Minimum improvement.** A model replaces the baseline (and later a challenger replaces the champion) only if it improves the metric by more than its noise. The noise is measured in step 3.2; in the research phase the sampling error of the test AUC was about 0.003.

## 7. Labels and their delay

| Event | When it is known |
|---|---|
| Loan defaults | At charge-off, which can be months or years after issue |
| Loan does not default | Only when it ends: at maturity (36 or 60 months) or at early repayment |

Consequences:

- **Training uses only loans whose outcome is complete** (matured or closed), as in the research phase. Training on running loans would teach the model that recent loans are safe.
- **Real performance arrives 3 to 5 years late.** Monitoring therefore relies on data drift and on an **early-warning metric: the default rate within the first 12 months** of each monthly cohort, compared with what the model predicted for that cohort. This needs the date of default (or of last payment), to be confirmed in step 0.2.
- Early in the simulation few loans have a complete outcome (Lending Club was small in 2007 to 2010). Step 0.2 quantifies how many loans are available for the first training.

## 8. Constraints

| Constraint | Requirement | Why | How it is checked |
|---|---|---|---|
| Explainability | Every prediction can be explained by feature contributions | Credit scoring is high-risk under the EU AI Act; an investor wants to know why | SHAP per prediction (step 3.5); model card |
| Latency | API p95 below 200 ms for a single loan | A slow score is useless at listing time | Load test (step 5.1) |
| Cost | Close to zero during development | Personal project | Everything in Docker until AWS (step 7.2); AWS budget alerts |
| Indirect discrimination | `addr_state` and the zip code prefix are reviewed as possible proxies for protected attributes | Discrimination in credit is illegal even if the model never sees the protected attribute | Analysis in step 0.2; Juan decides whether they stay |
| No information from the future | Every feature must exist at listing time | Otherwise the model looks good in validation and fails in production | Availability column in the data dictionary (step 0.2); anti-leakage test (step 2.4) |

## 9. Known risks

| Risk | Effect | Mitigation |
|---|---|---|
| `grade` dominates the PD | The model may beat the grade-only baseline by little | Measure it honestly; if the gain is within noise, say so |
| Few complete outcomes early in the simulation | Weak first models | Quantify in 0.2; choose the simulation start accordingly |
| Later vintages (2015 to 2016) performed worse with the same application profile | Drift that the model cannot see from features | This is what monitoring and retraining are for |
| Loans issued after about 2014 do not finish inside the data | The end of the simulation has no complete labels | Define the simulation window in 0.2 |
| Only approved loans are in the data | Caps achievable discrimination; no reject inference | Documented limitation |
| LGD is nearly constant (R² 0.06 in research) | LGD model adds little | Judge it by level per segment, as in research |
| Data source does not include default dates | No early-warning metric | Verify in 0.2 before building on it |

## 10. Out of scope

Reject inference, behavioural (payment history) features, secondary market trading, real money, regulatory capital.

## 11. Open decisions and where they are taken

| Decision | Step |
|---|---|
| Exact default status mapping | 0.2 |
| Simulation window and start date | 0.2 |
| Whether `addr_state` and zip code stay | 0.2 |
| Data source (full Lending Club file) | 0.2 |
| Buy rule | 3.x |
| Minimum improvement threshold | 3.2 |
