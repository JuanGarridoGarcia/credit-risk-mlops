# Validation rules

The catalogue of every data validation rule of the monthly load (playbook step 2.2): what each rule checks, its level, where it runs, why it exists and how many rows of the real file fail it. Every rule was approved by Juan before being written. The rule ids (`R1.1` ...) are the same in the code, in the run report and in the warnings table.

Related: [decision log](decisions.md) (D-053 to D-056), [technical document](technical.md) section 4, [data audit](data_audit.md).

Counts of failing rows were measured on 2026-11-23 on all 284 real deliveries after cleaning (2,260,668 listings, 1,348,099 outcomes).

## Contents

1. How validation runs
2. Levels
3. The dated contract
4. Reviewed exceptions
5. Rules
6. Rules considered and rejected
7. How to change a rule

---

## 1. How validation runs

```
raw ──> strict cleaning ──> pandera rules on the typed month (in memory)
          (formats)                 │
                                    v
               clean + SQL rules in the same transaction
               (a critical failure rolls back: the month does not enter)
```

- **Formats** are checked by the strict cleaning itself (D-051, the cleaning rules of step 2.1): a value that does not fit its rule stops the load with the column, the loan and the value. They are not repeated as pandera rules. Cleaning collects every failing column of a month at once, not only the first.
- **pandera** (D-053) checks the rules that only need the month that just arrived, in lazy mode: every failure of the run is collected.
- **SQL** checks the rules that need other months (history in Postgres), inside the transaction that writes the month, so it sees exactly what will be stored.
- Every run writes a report (JSON plus a readable summary) listing each failed rule with its failing rows, values and counts.

## 2. Levels

- **Critical** (D-054): the value is impossible or breaks the contract. The whole month stops (D-055): nothing of that month reaches the clean layer, neither listings nor outcomes. Raw keeps the delivery as it arrived. Values are never changed to make a row pass.
- **Warning** (D-054): the value is possible but unusual. The run goes on, the warning is in the report and is stored in a table, so F6 monitoring can follow it over time.

Rule of thumb used for every level: impossible by the definition of the variable, critical; possible but rare, warning.

## 3. The dated contract

Allowed values and product limits come from a contract that only knows the past (D-056). The base is what was known up to 2013-12, the last month loaded as history before the replay. Each later change has a month of entry into force, a reason and a pull request. A delivery is validated with the contract in force in its month; a value that arrives before its change fails as critical.

### Base contract (known up to 2013-12)

| Column | Allowed |
|---|---|
| `grade` | A to G |
| `sub_grade` | A1 to G5 (35 values) |
| `home_ownership` | MORTGAGE, NONE, OTHER, OWN, RENT |
| `verification_status` | Not Verified, Source Verified, Verified |
| `purpose` | 14 values (car, credit_card, debt_consolidation, educational, home_improvement, house, major_purchase, medical, moving, other, renewable_energy, small_business, vacation, wedding) |
| `addr_state` | 50 values (49 states without ND, plus DC) |
| `initial_list_status` | f, w |
| `application_type` | Individual |
| `disbursement_method` | Cash |
| `zip_code` | three digits followed by `xx` |
| `loan_amnt` | 500 to 35,000 |
| `loan_status` (outcomes) | Fully Paid, Charged Off, and the two "Does not meet the credit policy" statuses |
| `settlement_status` (outcomes) | ACTIVE, BROKEN, COMPLETE |
| Hardship columns (outcomes) | always empty |

`term` and `emp_length` are fixed by their cleaning rules.

### Contract changes

| Change | In force from | What it accepts | Reason |
|---|---|---|---|
| C1 | 2014-09 | `home_ownership = ANY` | New category offered by Lending Club |
| C2 | 2015-07 | `addr_state = ND` | First loans in North Dakota |
| C3 | 2015-10 | `application_type = Joint App`; `verification_status_joint` with the three values of `verification_status` | Joint applications launched |
| C4 | 2016-01 | `disbursement_method = DirectPay` | New disbursement method |
| C5 | 2016-03 | `loan_amnt` up to 40,000 | Maximum loan raised |
| C6 | 2017-06 | Hardship program in outcomes: `hardship_type` (INTEREST ONLY-3 MONTHS DEFERRAL), `hardship_reason` (9 values), `hardship_status` (BROKEN, COMPLETED), `hardship_loan_status` (5 values) | Hardship program launched |
| C7 | 2019-03 | `loan_status = Default` | Loans in default and not yet charged off at the snapshot (data_audit.md 4.2) |
| C8 | 2019-01 | The listings stream carries no loans | The source file ends in 2018-12 for listings; outcomes go on to 2019-03. Proposed with group 5, pending approval |

Known simplification: each change enters into force in the month the novelty first appears, as if the team reacted within the month. A data test checks that the base contract alone stops the replay exactly at the months of C1 to C8 and nowhere else.

## 4. Reviewed exceptions

Rows that fail a critical rule in real data that can never be delivered again. They pass that rule only, are listed in every report, and the data is not changed. Any other failing row still stops the month.

| Rule | Loan ids | Month | Reason |
|---|---|---|---|
| R3.5 | 124624, 127213 | 2007-09 | `open_acc` greater than `total_acc` (4 of 3, 14 of 8). Impossible, but in the 2007 history the provider will not send again |

## 5. Rules

Engine: **P** pandera on the month, **S** SQL against the history, **C** cleaning or delivery reader (step 2.1).

### Group 1: identity and month

| Id | Rule | Level | Engine | Why | Failing rows |
|---|---|---|---|---|---|
| R1.1 | Columns are exactly those of the contract, in order | Critical | C | A missing or extra column means the delivery changed | 0 |
| R1.2 | `id` is never empty and unique in the delivery | Critical | P | It is the key of everything | 0 |
| R1.3 | The `id` is not already in clean in another month | Critical | S | A loan is listed once and resolved once; catches a repeated or mixed delivery | 0 |
| R1.4 | Listings: `issue_d` is the month of the delivery | Critical | P | The month of the row decides what was known at T (step 2.3) | 0 |
| R1.5 | Outcomes: the resolution month computed from the row is the month of the delivery | Critical | S | Same for labels; otherwise information from the future enters | 0 (6,963 bad loans capped at the 2019-03 snapshot) |
| R1.6 | Every outcome has its listing in clean, from the same month or earlier | Critical | S | An outcome without its listing cannot be used; 8,950 loans resolve in the month they are listed, so listings load first | 0 |
| R1.7 | `url` ends with `loan_id=<id>` | Critical | P | If not, the identity of the row is doubtful | 0 |

### Group 2: allowed values

| Id | Rule | Level | Engine | Why | Failing rows |
|---|---|---|---|---|---|
| R2.1 | Categories and `zip_code` follow the contract in force (section 3) | Critical | P | A new category is a product change that needs a decision | 0 with C1 to C8 |
| R2.2 | `loan_amnt` within the product limits in force | Critical | P | Same, for the product limits | 0 with C5 |
| R2.3 | Money amounts are at least -0.01 | Critical | P | A negative amount is impossible; the cent of tolerance absorbs rounding noise (4 rows of `total_rec_late_fee` around -0.000000005) | 0 |
| R2.4 | Counts and months are whole numbers, at least 0 | Critical | P | By definition | 0 |
| R2.5 | `int_rate` greater than 0 and at most 100 | Critical | P | By definition | 0 |
| R2.6 | `pct_tl_nvr_dlq` and `percent_bc_gt_75` between 0 and 100 | Critical | P | Shares of accounts | 0 |
| R2.7 | Credit utilisation columns at least 0, no upper limit | Critical | P | Going over the limit is possible (maximum 892%) | 0 |
| R2.8 | Listing FICO between 300 and 850, and high = low + 4 or + 5 | Critical | P | The FICO scale is closed | 0 (441 rows with + 5) |
| R2.9 | Outcome `last_fico_range` whole numbers between 0 and 850 | Critical | P | Lending Club reports a 0 to 499 band (35,772 rows) and 0 to 0 for no score (212) | 0 |
| R2.10 | `dti` negative or above 100 | Warning | P | Possible with very low income or high debt; includes the 135 values of 999 (E-014) | 2 + 2,561 |
| R2.11 | `annual_inc` above 10 million | Warning | P | Possible but rare | 3 |
| R2.12 | 999 in account age columns, 9,999,999 in credit limit columns | Warning | P | Look like cap codes | 3 + 17 |
| R2.13 | `int_rate` above the highest rate seen in clean so far | Warning | S | A pricing change the model never saw | Fires in 2015 (28.99%) and 2016 (30.99%) |

### Group 3: consistency between columns

| Id | Rule | Level | Engine | Why | Failing rows |
|---|---|---|---|---|---|
| R3.1 | `sub_grade` starts with its `grade` | Critical | P | B3 belongs to B | 0 |
| R3.2 | `earliest_cr_line` and `sec_app_earliest_cr_line` are not after `issue_d` | Critical | P | A credit history cannot start after the application | 0 |
| R3.3 | The 16 joint-application columns are empty in individual applications | Critical | P | They describe a second applicant | 0 |
| R3.4 | Every joint application has `annual_inc_joint` | Critical | P | Without it the joint income is unknown | 0 |
| R3.5 | `open_acc` ≤ `total_acc` and `num_actv_bc_tl` ≤ `num_bc_tl` | Critical | P | Open accounts are a subset of all accounts | 2 (reviewed exceptions, section 4) |
| R3.6 | `total_pymnt` = principal + interest + late fees + recoveries, within 1 dollar | Critical | P | Accounting identity | 0 |
| R3.7 | `out_prncp` is 0 unless `loan_status = Default` | Critical | P | A resolved loan owes no principal | 0 (40 Default rows) |
| R3.8 | Recoveries only in bad loans | Critical | P | Nothing to recover from a paid loan | 0 |
| R3.9 | Settlement columns all filled or all empty, matching `debt_settlement_flag`; hardship columns all filled or all empty | Critical | P | They describe one event | 0 |
| R3.10 | `funded_amnt_inv` ≤ `funded_amnt` | Critical | P | Investors fund part of the loan at most | 0 |
| R3.11 | `funded_amnt` ≤ `loan_amnt` of its listing | Critical | S | A loan is not funded above the request | 0 |
| R3.12 | `last_pymnt_d` is not before `issue_d` of its listing | Critical | S | No payment before the loan exists | 0 |
| R3.13 | `annual_inc = 0` in an individual application | Warning | P | Possible (no income, no benefits) but should be looked at | 0 (the 1,667 zeros are all joint) |
| R3.14 | `Fully Paid` but principal received differs from `funded_amnt` by more than 1 dollar | Warning | P | A fully paid loan repays its principal | 4 (2018, short by 1 or 2 dollars) |
| R3.15 | `installment` differs by more than 1% from the amortisation formula on `funded_amnt`, `int_rate` and `term` | Warning | S | The instalment should follow the formula | 433 |

Finding for F3: `installment` is computed on the funded amount, not the requested one, so in the 2,062 loans that were not fully funded it reveals something that happened after listing (recorded in the data audit).

### Group 4: missing values

Missing values are information and are never filled (D-051). These rules watch that they do not appear where they never were, and that their share does not change suddenly.

| Id | Rule | Level | Engine | Why | Failing rows |
|---|---|---|---|---|---|
| R4.1 | The 19 listing columns that were never empty stay filled | Critical | P | `id`, amount, term, rate, instalment, grade, FICO, state and others | 0 |
| R4.2 | 36 more listing columns are required from the month after their last empty value (2007-09 to 2013-01) | Critical | P | Complete ever since; all dates are within the base contract | 0 |
| R4.3 | `dti` filled in individual applications | Critical | P | In joint ones it may be missing: with individual income 0 the ratio does not exist | 0 |
| R4.4 | The 20 outcome columns that were never empty stay filled; `last_pymnt_d` filled in paid loans | Critical | P | A paid loan has a last payment | 0 |
| R4.5 | `member_id` stays empty | Critical | P | A personal identifier Lending Club stopped publishing; it must not spread | 0 |
| R4.6 | The share of missing values of a column moves more than 10 points from the previous month, either way | Warning | P + S | Compared with the previous month because missing values have no seasonality | 4 months of 60 in 2014 to 2018: 2014-03 and 2014-04 (`desc` dropped), 2015-12 and 2016-01 (14 new bureau fields) |

### Group 5: volume of the month (proposed, pending approval)

Compared with the median of the previous 12 months: the previous month fails because of seasonality, the same month of the previous year because one weak month (2014-12) makes the next year look 4.3 times larger. The median ignores a single peak such as 2016-03.

| Id | Rule | Level | Engine | Why | Fires in the whole file |
|---|---|---|---|---|---|
| R5.1 | Fewer than 10% or more than 5 times the median (includes an empty month) | Critical | S | Not explained by the real world | 2019-01 to 2019-03 in listings (C8) |
| R5.2 | Fewer than half or more than twice the median | Warning | S | Possible (growth, seasonality, shocks) but worth a look | 2012-08 to 2012-10, 2014-10 |
| R5.3 | R5.1 and R5.2 apply only when the median is at least 1,000 loans | | | With few loans ratios mean nothing (2008-06: 11 outcomes against a median of 0.5) | |

Changes in the mix of loans (for example more grade E) are drift, not broken data: F6 monitoring measures them.

## 6. Rules considered and rejected

| Rule | Why rejected |
|---|---|
| Contract taken from the whole file, with a warning when a value is seen for the first time | Uses knowledge of the file's future to run operations (D-056, option B) |
| If `delinq_2yrs > 0`, then `mths_since_last_delinq` ≤ 24 | Fails in 8,103 rows spread over every month: the fields come from bureau queries made on different dates. A warning that fires every month is noise, and noise hides the warnings that matter |
| Volume compared with the previous month or the same month of the previous year | Seasonality and single weak months (group 5) |
| Missing-value share compared with the 12-month median | The warning for a real change would fire 8 months in a row until the median caught up |

## 7. How to change a rule

A rule, a contract change or an exception is changed in a pull request that updates the code and this document together, with the reason and the numbers on real data. A test checks that every rule id in the code is in this document and the other way round, so the two cannot drift apart.
