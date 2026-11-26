# The thresholds of the alerts

Why each threshold of the monitoring alerts is what it is, the study that set them, and the exam they then passed or failed. The values live in [`src/credit_risk/monitoring/thresholds.toml`](../src/credit_risk/monitoring/thresholds.toml), each with its reason. The rules that turn them into alerts are in [`alerting.py`](../src/credit_risk/monitoring/alerting.py), explained in the [technical document](technical.md), F6, second pull request. Decisions D-149, D-150 and D-156 in the [decision log](decisions.md).

## 1. What alerts, and how serious (D-149)

| Signal | Alerts? | Kind and severity | Fires when |
|---|---|---|---|
| Drift of an input variable | Never; the Data dashboard shows it, to explain | | |
| Drift of a prediction (PD, LGD, expected loss rate) | Yes | `prediction_drift`, warning | its PSI is above its threshold |
| Early warning of a cohort | Yes | `early_warning`, warning | the whole 95% interval of observed / expected first-year defaults is above 1.0 |
| Real performance of a matured cohort | Yes | `performance_drop`, error | the whole AUC interval is below the champion's validation AUC minus 0.01, or the whole calibration error interval is above 0.01, or the LGD level error is beyond 0.15 |
| Level correction of a new LGD | Yes | `lgd_level_shift`, warning | the correction is beyond 0.15; the promotion goes on by the usual rules (D-151) |

A value equal to its threshold does not alert. Each alert is recorded once: a month run again adds nothing (T30.2).

## 2. Calibrated with only what was known at T0 (D-150)

The thresholds are set before the system starts, so they may use only what the system had at T0 (2014-01). The study reads no month, cohort or outcome later than 2013-12, and refuses to (T33.1). The simulation 2014 to 2018 is then the exam of the frozen thresholds: it was not looked at before the values were fixed, and a change after it is a new decision.

The models are the pair of champions trained at T0. The PD learns from loans listed up to about 2010-08 (the cohorts matured at T0), so the months from 2010-09 to 2013-12 are real history it never saw. On that history the study measures:

- **Drift.** A pseudo cutoff every month from 2011-09. The reference of each is its 12 months before, as in production (D-138), and every later month up to 2013-12 is measured against it, at its lag (months after the reference). Next to each PSI goes its noise: the 99th percentile of the PSI of 200 samples of the same size drawn from the reference itself, what chance alone gives.
- **Early warning.** Every cohort whose 17 months had passed by 2013-12, measured as the monitoring does (D-143).
- **Performance.** AUC and calibration error, with bootstrap intervals, of the last six 36-month cohorts matured by 2013-12, and their pooled value.
- **LGD level.** The level correction (D-094) the baseline LGD needed at a pseudo cutoff every quarter from 2011-01.

`make calibrate` runs it (about a minute) on the database the exam leaves, and writes [`reports/thresholds/summary.json`](../reports/thresholds/summary.json) and the tables of section 5. Two runs give the same result, and the tables below are the ones it writes (T33.2).

## 3. From the study to the values (D-156)

The rules were written before the values were read, and T33.3 checks that the file follows them (`calibrate.propose`):

| Threshold | Rule | Value |
|---|---|---|
| PSI of the PD and of the expected loss rate | The smallest value of the grid 0.10, 0.15, 0.20, 0.25 that no month exceeded with a reference 0 to 2 months old. With the quarterly retraining (D-106) a reference is that old when it is replaced. | 0.25 (largest seen 0.219 and 0.217) |
| PSI of the LGD | Same rule | 0.15 (largest seen 0.121) |
| Early warning | The whole interval above 1.0: more first-year defaults than the PD expects, for sure. Chosen by Juan on 2026-11-26, knowing what it does on the history (section 4) | 1.0 |
| AUC and calibration margins | The margins of a segment clearly worse at promotion (D-093). The champion's PD is Platt calibrated, so its validation calibration error is about 0, and the margin is measured from 0 | 0.01 and 0.01 |
| LGD level error and level correction | The first value of the grid 0.05, 0.10, 0.15, 0.20 above every level correction seen | 0.15 (largest seen 0.134) |

## 4. What the study found

**The drift of the predictions grows with the age of the reference.** The median PSI of the PD is 0.03 against a fresh reference and 0.34 against one 11 months old; chance alone gives about 0.004. A threshold on a stale reference would fire every month, which is why the rule looks only at lags 0 to 2.

**The input variables move a lot, and that is why they never alert.** `initial_list_status` reaches a PSI of 2.4 and `int_rate` 1.5 against a fresh reference: Lending Club changed its products and its rates, and the predictions moved far less. An alert on them would ring every month (D-149).

**The T0 model underestimates the early defaults of the newer cohorts.** The ratio of observed to expected first-year defaults is 0.75 to 1.1 on the cohorts of late 2010, and 1.2 to 1.4 on those of 2011-12 to 2012-07. With the threshold at 1.0 the early warning fires on 2011-04, alone, and on 7 of the last 8 cohorts. On the cohorts inside the PD's training period (2009-06 to 2010-08, checked apart) it fires once, on 2009-11. The cause is not known yet; this is a real gap the monitoring finds, not noise, and the exam shows what it does next.

**No matured cohort before T0 is clearly worse than validation.** The AUC of the six cohorts goes from 0.61 to 0.73 around a pooled 0.675, with intervals about ±0.06 wide; the calibration error interval stays below 0.01 (largest lower end 0.009, close).

**The level correction of the LGD was 0.05 to 0.13 at every quarterly cutoff.**

## 5. The tables of the study

<!-- study tables: generated by make calibrate, do not edit -->
Pair of champions at T0: PD 2, LGD 1. Data up to 2013-12.

**PSI of the predictions by lag** (months after the reference): median and largest over the months measured; noise is the median of what chance alone gives.

| Prediction | Lag | Months | Median | Largest | Noise |
| --- | --- | --- | --- | --- | --- |
| el_rate | 0 | 28 | 0.035 | 0.159 | 0.004 |
| el_rate | 1 | 27 | 0.052 | 0.182 | 0.004 |
| el_rate | 2 | 26 | 0.054 | 0.217 | 0.004 |
| el_rate | 3 | 25 | 0.057 | 0.264 | 0.004 |
| el_rate | 4 | 24 | 0.106 | 0.313 | 0.004 |
| el_rate | 5 | 23 | 0.16 | 0.366 | 0.003 |
| el_rate | 6 | 22 | 0.188 | 0.425 | 0.004 |
| el_rate | 7 | 21 | 0.208 | 0.49 | 0.004 |
| el_rate | 8 | 20 | 0.242 | 0.515 | 0.003 |
| el_rate | 9 | 19 | 0.249 | 0.547 | 0.003 |
| el_rate | 10 | 18 | 0.286 | 0.564 | 0.003 |
| el_rate | 11 | 17 | 0.351 | 0.593 | 0.003 |
| lgd | 0 | 28 | 0.028 | 0.097 | 0.003 |
| lgd | 1 | 27 | 0.037 | 0.107 | 0.003 |
| lgd | 2 | 26 | 0.041 | 0.121 | 0.002 |
| lgd | 3 | 25 | 0.049 | 0.134 | 0.002 |
| lgd | 4 | 24 | 0.061 | 0.135 | 0.002 |
| lgd | 5 | 23 | 0.076 | 0.164 | 0.002 |
| lgd | 6 | 22 | 0.1 | 0.196 | 0.002 |
| lgd | 7 | 21 | 0.123 | 0.233 | 0.002 |
| lgd | 8 | 20 | 0.145 | 0.25 | 0.002 |
| lgd | 9 | 19 | 0.159 | 0.271 | 0.002 |
| lgd | 10 | 18 | 0.179 | 0.275 | 0.002 |
| lgd | 11 | 17 | 0.193 | 0.313 | 0.002 |
| pd | 0 | 28 | 0.033 | 0.161 | 0.004 |
| pd | 1 | 27 | 0.05 | 0.187 | 0.004 |
| pd | 2 | 26 | 0.055 | 0.219 | 0.004 |
| pd | 3 | 25 | 0.056 | 0.267 | 0.004 |
| pd | 4 | 24 | 0.104 | 0.313 | 0.004 |
| pd | 5 | 23 | 0.155 | 0.368 | 0.004 |
| pd | 6 | 22 | 0.185 | 0.428 | 0.004 |
| pd | 7 | 21 | 0.21 | 0.487 | 0.004 |
| pd | 8 | 20 | 0.241 | 0.512 | 0.003 |
| pd | 9 | 19 | 0.249 | 0.546 | 0.003 |
| pd | 10 | 18 | 0.282 | 0.562 | 0.003 |
| pd | 11 | 17 | 0.341 | 0.595 | 0.003 |

**The input variables that moved most** with a reference 0 to 2 months old (they never alert, D-149):

| Variable | Largest PSI | Noise |
| --- | --- | --- |
| initial_list_status | 2.42 | 0.0 |
| int_rate | 1.457 | 0.003 |
| mths_since_last_delinq | 0.522 | 0.003 |
| mths_since_last_record | 0.344 | 0.004 |
| revol_bal | 0.336 | 0.003 |

**Early warning** of every cohort measured by T0 (observed / expected first-year defaults, 95% interval; fires above 1.0):

| Cohort | Term | Loans | Defaults | Ratio | Low | High | Fires |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2010-09 | 36 | 732 | 22 | 0.809 | 0.537 | 1.214 |  |
| 2010-10 | 36 | 732 | 26 | 0.947 | 0.649 | 1.374 |  |
| 2010-11 | 36 | 765 | 20 | 0.767 | 0.498 | 1.175 |  |
| 2010-12 | 36 | 896 | 20 | 0.754 | 0.49 | 1.156 |  |
| 2011-01 | 36 | 949 | 26 | 0.951 | 0.651 | 1.382 |  |
| 2011-02 | 36 | 831 | 26 | 1.094 | 0.75 | 1.589 |  |
| 2011-03 | 36 | 837 | 32 | 1.379 | 0.981 | 1.928 |  |
| 2011-04 | 36 | 947 | 38 | 1.401 | 1.026 | 1.907 | yes |
| 2011-05 | 36 | 957 | 36 | 1.317 | 0.955 | 1.807 |  |
| 2011-06 | 36 | 1259 | 34 | 0.883 | 0.634 | 1.226 |  |
| 2011-07 | 36 | 1288 | 49 | 1.234 | 0.937 | 1.619 |  |
| 2011-08 | 36 | 1295 | 46 | 1.203 | 0.905 | 1.593 |  |
| 2011-09 | 36 | 1368 | 48 | 1.227 | 0.929 | 1.616 |  |
| 2011-10 | 36 | 1411 | 51 | 1.284 | 0.981 | 1.678 |  |
| 2011-11 | 36 | 1544 | 60 | 1.242 | 0.969 | 1.588 |  |
| 2011-12 | 36 | 1415 | 65 | 1.412 | 1.113 | 1.787 | yes |
| 2012-01 | 36 | 2058 | 92 | 1.311 | 1.073 | 1.599 | yes |
| 2012-02 | 36 | 2083 | 99 | 1.42 | 1.171 | 1.718 | yes |
| 2012-03 | 36 | 2357 | 106 | 1.423 | 1.181 | 1.713 | yes |
| 2012-04 | 36 | 2680 | 109 | 1.191 | 0.991 | 1.43 |  |
| 2012-05 | 36 | 2741 | 128 | 1.38 | 1.165 | 1.632 | yes |
| 2012-06 | 36 | 3048 | 157 | 1.324 | 1.137 | 1.541 | yes |
| 2012-07 | 36 | 3781 | 205 | 1.34 | 1.173 | 1.53 | yes |

**Performance of the last matured 36-month cohorts** (pooled AUC 0.675, calibration error 0.002):

| Cohort | Loans | Defaults | AUC | AUC low | AUC high | Calibration | Cal. low | Cal. high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2010-02 | 625 | 62 | 0.726 | 0.662 | 0.794 | 0.012 | 0.008 | 0.017 |
| 2010-03 | 736 | 69 | 0.663 | 0.602 | 0.721 | 0.013 | 0.009 | 0.018 |
| 2010-04 | 825 | 82 | 0.73 | 0.678 | 0.78 | 0.006 | 0.002 | 0.01 |
| 2010-05 | 750 | 87 | 0.675 | 0.612 | 0.738 | 0.013 | 0.009 | 0.018 |
| 2010-06 | 602 | 64 | 0.654 | 0.585 | 0.72 | 0.01 | 0.005 | 0.015 |
| 2010-07 | 742 | 65 | 0.611 | 0.538 | 0.676 | 0.0 | 0.0 | 0.005 |

**Level correction of the baseline LGD** at a pseudo cutoff every quarter:

| Cutoff | Train | Validation | Observed LGD | Correction |
| --- | --- | --- | --- | --- |
| 2011-07 | 5 | 75 | 0.587 | 0.1 |
| 2011-10 | 25 | 132 | 0.592 | 0.126 |
| 2012-01 | 94 | 100 | 0.602 | 0.073 |
| 2012-04 | 170 | 75 | 0.667 | 0.134 |
| 2012-07 | 204 | 127 | 0.657 | 0.113 |
| 2012-10 | 254 | 178 | 0.656 | 0.098 |
| 2013-01 | 344 | 206 | 0.665 | 0.091 |
| 2013-04 | 455 | 297 | 0.68 | 0.103 |
| 2013-07 | 585 | 354 | 0.655 | 0.068 |
| 2013-10 | 799 | 350 | 0.648 | 0.047 |
<!-- end of the study tables -->

## 6. The exam: 2014 to 2018 with the thresholds frozen

`make exam` replays the simulation from an empty clock on a database of its own (`threshold_exam`), with the real number of trials and the API in a process of its own, as T17.9 does for 2014. It takes hours, so it resumes where it stopped (the cloud machine of the project is suspended when idle, so it runs as a task the session follows); `FRESH=1` starts it from nothing (E-066). T33.4 then checks that every month ran (no `flow_failed`), that every month with predictions has its drift, and that the alerts are exactly the ones below. In the column *What*, an early warning shows the lower end of the 95% interval of its ratio, the number the rule compares with 1.0.

The exam ran on 2026-11-26, after E-065 (an LGD fault the exam itself found at 2016-04), from an empty clock: 60 months, 20 quarterly retrainings, no month failed.

<!-- exam table: generated by make calibrate, do not edit -->
| Month | Kind | Alerts | What |
| --- | --- | --- | --- |
| 2016-02 | early_warning | 1 | 36m 2014-09 1.00 |
| 2016-03 | early_warning | 1 | 36m 2014-10 1.02 |
| 2016-10 | early_warning | 1 | 36m 2015-05 1.07 |
| 2016-11 | early_warning | 1 | 36m 2015-06 1.02 |
| 2016-12 | early_warning | 1 | 36m 2015-07 1.01 |
| 2017-02 | early_warning | 1 | 36m 2015-09 1.11 |
| 2017-03 | early_warning | 1 | 36m 2015-10 1.06 |
| 2017-05 | early_warning | 1 | 36m 2015-12 1.03 |
| 2017-06 | early_warning | 1 | 36m 2016-01 1.06 |
| 2017-07 | early_warning | 1 | 36m 2016-02 1.03 |
| 2017-07 | performance_drop | 1 | auc 36m 2014-02 |
| 2017-08 | early_warning | 1 | 36m 2016-03 1.04 |
| 2017-08 | performance_drop | 1 | auc 36m 2014-03 |
| 2017-09 | early_warning | 1 | 36m 2016-04 1.10 |
| 2017-09 | performance_drop | 2 | auc 36m 2014-04; calibration_error 36m 2014-04 |
| 2017-10 | early_warning | 1 | 36m 2016-05 1.11 |
| 2017-10 | performance_drop | 2 | auc 36m 2014-05; calibration_error 36m 2014-05 |
| 2017-11 | early_warning | 1 | 36m 2016-06 1.06 |
| 2017-11 | performance_drop | 2 | auc 36m 2014-06; calibration_error 36m 2014-06 |
| 2017-12 | early_warning | 1 | 36m 2016-07 1.07 |
| 2017-12 | performance_drop | 1 | auc 36m 2014-07 |
| 2018-01 | early_warning | 1 | 36m 2016-08 1.07 |
| 2018-02 | early_warning | 1 | 36m 2016-09 1.06 |
| 2018-02 | performance_drop | 1 | calibration_error 36m 2014-09 |
| 2018-03 | performance_drop | 1 | calibration_error 36m 2014-10 |
| 2018-04 | early_warning | 2 | 36m 2016-11 1.28; 60m 2016-11 1.37 |
| 2018-04 | performance_drop | 1 | calibration_error 36m 2014-11 |
| 2018-05 | early_warning | 2 | 36m 2016-12 1.34; 60m 2016-12 1.47 |
| 2018-05 | performance_drop | 1 | calibration_error 36m 2014-12 |
| 2018-06 | early_warning | 2 | 36m 2017-01 1.20; 60m 2017-01 1.28 |
| 2018-06 | performance_drop | 1 | calibration_error 36m 2015-01 |
| 2018-07 | early_warning | 2 | 36m 2017-02 1.26; 60m 2017-02 1.22 |
| 2018-07 | performance_drop | 1 | calibration_error 36m 2015-02 |
| 2018-08 | early_warning | 2 | 36m 2017-03 1.21; 60m 2017-03 1.31 |
| 2018-08 | performance_drop | 1 | calibration_error 36m 2015-03 |
| 2018-09 | early_warning | 2 | 36m 2017-04 1.37; 60m 2017-04 1.29 |
| 2018-09 | performance_drop | 1 | calibration_error 36m 2015-04 |
| 2018-10 | early_warning | 2 | 36m 2017-05 1.39; 60m 2017-05 1.14 |
| 2018-10 | performance_drop | 1 | calibration_error 36m 2015-05 |
| 2018-11 | early_warning | 2 | 36m 2017-06 1.37; 60m 2017-06 1.21 |
| 2018-11 | performance_drop | 1 | calibration_error 36m 2015-06 |
| 2018-12 | early_warning | 2 | 36m 2017-07 1.36; 60m 2017-07 1.28 |
| 2018-12 | performance_drop | 1 | calibration_error 36m 2015-07 |

Totals: prediction_drift 0, early_warning 35, performance_drop 20, lgd_level_shift 0.
<!-- end of the exam table -->

### 6.1 What the exam found

**The thresholds raised no false alarm on the predictions or the LGD.** Over 59 served months, the largest PSI of the predictions was 0.066 for the PD, 0.098 for the LGD and 0.074 for the expected loss, against thresholds of 0.25, 0.15 and 0.25 (medians 0.012 to 0.016). The reference renewed at each promotion (D-138) keeps it fresh, as the study expected. The level of the LGD in matured cohorts stayed between 0.027 and 0.053, far from 0.15. The inputs moved as much as before (`int_rate` PSI 1.16 in 2017-10, `disbursement_method` 0.94 in 2018-07) and, as decided (D-149), never alerted.

**What did alert was the outcome: the PD underestimates default, more and more.** The prediction drift cannot see this: the predictions stay where they were while the borrowers change. Only the rules that look at real defaults can.

- *Early warning, 35 alerts, from 2016-02 to the end.* Cohorts 2014-09 to 2016-09 defaulted 1.07 to 1.19 times the expected in their first year. From the cohort 2016-11 the ratio jumps to 1.22 to 1.58, and the 60-month loans join (the PD covers them from version 13). About a third of that jump is the model: the mean predicted PD fell from about 0.148 (version 9) to about 0.137 (version 13). The rest is the cohorts.
- *Performance drop, 20 alerts, from 2017-07, when the first cohort of the exam matured.* The cohorts 2014-02 to 2014-07, scored by the T0 model (PD version 2), rank worse than in validation: AUC 0.607 to 0.633 against 0.677 (three of them are also a little miscalibrated, 0.011 to 0.015). The next models rank as well as validation (AUC 0.661 to 0.682) but their level is wrong: mean PD 0.115 to 0.126 against default rates of 0.134 to 0.154. That puts the calibration error at 0.021 to 0.038, above the 0.01 of the rule, on every cohort from 2014-09 to 2015-07.

**The early warning saw it first, about two years before the matured cohorts confirmed it.** Five of the matured cohorts had an early warning (2014-09, 2014-10, 2015-05, 2015-06, 2015-07), raised between 2016-02 and 2016-12. All five later failed the calibration rule at maturity, between 2018-02 and 2018-12. It missed the other nine (2014-04 to 2014-06 and 2014-11 to 2015-04), whose first-year ratio stayed within noise of 1.0. On what matured inside the exam, then, it raised no false warning and caught 5 of the 14 calibration failures, each 24 months before maturity.

**Retraining did not fix it, as the delay of the labels predicts.** A 36-month loan is known 41 months after listing, so the PD trained in 2017 learns from loans of 2013. The newer borrowers default more than the older ones with the same features, and the models trained later even moved the level down. The realised return of the cohorts fell from 12.4% (2014-02) to 5.9% (2015-06). What to do about it is the subject of step 6.3: the alerts above are what would trigger it.

### 6.2 What this says about the thresholds

The values of D-156 are kept: they rang on a real and growing problem and stayed silent where nothing was wrong. Two things are worth saying plainly. First, the prediction drift was never close to its threshold, so in this period it added nothing; it stays as a guard against a broken input pipeline, which is the failure it is built for. Second, the early warning missed cohorts whose first year looked normal but whose lifetime default rate ended 9% to 32% above the predicted one: the gap in them opened after the first year, which a first-year signal cannot see, whatever its threshold. Lowering it would ring on noise too; with only 11 matured cohorts in the exam there is not enough evidence to move it, and moving it now would tune the thresholds on the exam, which D-150 forbids.
