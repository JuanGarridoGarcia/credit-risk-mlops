# Data audit

Step 0.2 of the playbook. Status: **draft**. Decisions 9.1 to 9.3, 9.7 and 9.8 taken by Juan on 2026-11-21 (D-013 to D-018); 9.4 to 9.6 deferred by Juan to the design of the simulation and decided on 2026-11-23 in F2 (D-040 to D-042).

Every figure in this document is produced by [`notebooks/00_data_audit.ipynb`](../notebooks/00_data_audit.ipynb), which writes its tables to [`reports/data_audit/`](../reports/data_audit/). Nothing here is typed by hand from memory.

## 1. Source inventory

| Item | Value |
|---|---|
| Dataset | [All Lending Club loan data](https://www.kaggle.com/datasets/wordsforthewise/lending-club) (`wordsforthewise/lending-club`), file `accepted_2007_to_2018Q4.csv.gz` |
| File size | 392,582,231 bytes compressed; 2.7 GB in memory |
| SHA-256 | `55c16f75120f897683f02e7aabcf080d0e4a20c4832feb1d592cfa941bd62a2d` |
| Rows | 2,260,701 in the file, of which 33 are summary rows appended by Lending Club ("Total amount funded in policy code ..."). **2,260,668 loans** |
| Columns | 151 |
| Loans issued | June 2007 to December 2018 |
| Snapshot date | End of March 2019 (latest last payment: March 2019; latest credit pull: April 2019). Every loan is seen as it stood on that date |
| Licence | CC0-1.0, as declared by the Kaggle uploader. The uploader is not the data owner: the data was published by Lending Club under its own terms. We never redistribute it; every machine downloads it from Kaggle |
| Column descriptions | [`jonchan2003/lending-club-data-dictionary`](https://www.kaggle.com/datasets/jonchan2003/lending-club-data-dictionary): Lending Club's official dictionary (sheets `LoanStats` and `Browse Notes`). Licence "unknown"; used only as documentation, not as data. SHA-256 of both files recorded in the notebook |
| How it is downloaded | Kaggle API (`kaggle` CLI 2.2.5), token in the `KAGGLE_API_TOKEN` environment variable. The notebook downloads only if the files are missing and stops if a hash does not match |

The `Browse Notes` sheet matters: it lists the fields **an investor saw on a listed loan**. It is the evidence used for "available at listing" below.

## 2. Data dictionary

The full table (151 columns: meaning, type, % missing, first year reported, availability at listing, proposed use) is in the [appendix](#appendix-full-data-dictionary) and in [`reports/data_audit/data_dictionary.csv`](../reports/data_audit/data_dictionary.csv).

Rule for `available at listing`:

| Value | Rule | Columns |
|---|---|---|
| yes | The field is in Lending Club's Browse Notes dictionary | 107 |
| no | Describes what happened after issue (payments, recoveries, hardship, settlement, refreshed credit data) or the result of the funding | 41 |
| doubtful | Not proven by Browse Notes, reason given | 3 (`issue_d`, `funded_amnt`, `mths_since_recent_bc_dlq`) |

Proposed use:

| Use | Columns |
|---|---|
| Feature candidate | 99 |
| Drop for leakage | 32 |
| Target source (status, payments, recoveries, last payment date; `funded_amnt` as EAD) | 9 |
| Identifier (`id`, `url`; `member_id` is empty in every row) | 3 |
| Free text, not used in v1 (`emp_title`, `desc`, `title`) | 3 |
| Proxy review (`addr_state`, `zip_code`) | 2 |
| Decision (`issue_d`, `mths_since_recent_bc_dlq`) | 2 |
| Constant (`policy_code`) | 1 |

## 3. Leakage risks

| Column or group | Why it leaks | Evidence | Proposal |
|---|---|---|---|
| Payments, recoveries, outstanding principal, `last_pymnt_*`, `next_pymnt_d`, `pymnt_plan` | Known only after issue; they define the targets | Not in Browse Notes | Target source or drop, never a feature |
| `last_fico_range_*`, `last_credit_pull_d` | Look like application data, but are refreshed after issue | Median change from the application FICO: **-130 points for charged-off loans, +5 for fully paid**. A near perfect "future" signal | Drop |
| Hardship (15 columns), settlement (6 columns) and `debt_settlement_flag` | Exist only for loans in trouble | Filled from 2016 (hardship) and 2013 (settlement) | Drop |
| `funded_amnt_inv` | Result of the listing (how much investors funded) | Not in Browse Notes | Drop |
| Fields that start being reported in a given year | Their missingness tells the model the vintage | Bureau family 1 from 2012 (37 columns, for example `tot_cur_bal`, `mths_since_recent_inq`); bureau family 2 from December 2015 (14 columns, for example `open_acc_6m`, filled for 99.8% of loans from January 2016); joint applications from late 2015 and second applicant data from 2017; `desc` stops in 2014. Table: `missingness_by_year.csv` | Decision 9.3 |
| `issue_d` | Encodes the vintage; later vintages defaulted more for the same profile | Bad rate of resolved 36-month loans: 12.3% for 2013, 14.9% for 2015 | Not a feature. Used only to order and split in time |
| `grade` and `int_rate` | Not leakage, but their meaning drifts: Lending Club re-priced the grades over time | Mean rate of grade E: 14.1% in 2007, 25.2% in 2018 | Feature, monitored for drift |

## 4. Labels and their delay

### 4.1 Status mapping (decided, D-013)

| Status | Loans | Label |
|---|---|---|
| Fully Paid | 1,076,751 | 0 |
| Charged Off | 268,559 | 1 |
| Default (121+ days late, not yet charged off) | 40 | 1 |
| Does not meet the credit policy. Status: Fully Paid | 1,988 | Removed |
| Does not meet the credit policy. Status: Charged Off | 761 | Removed |
| Current, In Grace Period, Late (16-30), Late (31-120) | 912,569 | No label: still running at the snapshot |

The "does not meet the credit policy" loans were all issued from 2007 to 2010 under an older, looser policy. Juan removed them: they would muddy the data, and a user of the API expects scores under the current policy. **From here on, every figure excludes them** (2,257,919 loans in scope).

Result: **1,345,350 loans with a final outcome**, 268,599 of them bad (20.0%).

### 4.2 Default date

**There is no charge-off date column.** It can be estimated:

- The first missed payment is the month after `last_pymnt_d`.
- Lending Club charged a loan off at about 150 days past due. The estimate used is **5 months after the last payment** (`last_pymnt_d` + 5), or issue + 5 when the loan never paid. (Corrected on 2026-11-23, E-013: this text first said "5 months after the first missed payment", which is one month later than what the notebook computes. The notebook's rule is the one supported by the data; see E-013.)

Checks:

- 2,313 bad loans never paid anything (`last_pymnt_d` empty): their first missed payment is issue + 1 and their charge-off month is estimated as issue + 5.
- 4,015 bad loans had their last payment less than 5 months before the snapshot and were already charged off. So the 5-month lag is a typical value, not a fixed rule (a bankruptcy, for example, is charged off sooner). The estimate is capped at the snapshot.
- The estimate has monthly precision, which is enough for monthly monitoring.

**Consequence for D-003 (12-month early-warning metric): it is feasible.** 41% of bad 36-month loans and 36% of bad 60-month loans missed their first payment within 12 months of issue. In monitoring, the 12-month default rate of a monthly cohort is fully known about 17 months after issue (12 months plus the charge-off lag).

### 4.3 Delay from issue to a final label (months)

Resolution month: last payment for good loans; estimated charge-off month for bad loans. Table: `label_delay.csv`.

| Term | Outcome | Loans | p10 | p25 | median | p75 | p90 |
|---|---|---|---|---|---|---|---|
| 36 | good | 857,491 | 5 | 12 | 22 | 35 | 36 |
| 36 | bad | 163,277 | 9 | 13 | 19 | 26 | 32 |
| 60 | good | 219,260 | 4 | 9 | 19 | 33 | 48 |
| 60 | bad | 105,322 | 10 | 14 | 20 | 30 | 39 |

Only 25% of good 36-month loans run to maturity; the rest are prepaid. Bad loans resolve in a narrower window around 1.5 to 2.5 years.

### 4.4 Share of each vintage with a final outcome at the snapshot

Table: `resolved_by_vintage.csv`.

| Issue year | Loans 36m | Resolved 36m | Bad rate 36m* | Loans 60m | Resolved 60m | Bad rate 60m* |
|---|---|---|---|---|---|---|
| 2007 | 251 | 100% | 17.9% | | | |
| 2008 | 1,562 | 100% | 15.8% | | | |
| 2009 | 4,716 | 100% | 12.6% | | | |
| 2010 | 8,466 | 100% | 9.9% | 3,070 | 100% | 21.0% |
| 2011 | 14,101 | 100% | 10.6% | 7,620 | 100% | 23.6% |
| 2012 | 43,470 | 100% | 13.6% | 9,897 | 100% | 27.7% |
| 2013 | 100,422 | 100% | 12.3% | 34,392 | 100% | 25.1% |
| 2014 | 162,570 | 100% | 13.7% | 73,059 | 82.9% | 31.1% |
| 2015 | 283,173 | 99.9% | 14.9% | 137,922 | 67.1% | 36.4% |
| 2016 | 323,495 | 71.8% | 19.8% | 110,912 | 54.8% | 36.4% |
| 2017 | 320,419 | 40.1% | 20.0% | 123,160 | 33.1% | 33.0% |
| 2018 | 344,671 | 12.0% | 13.2% | 150,571 | 10.0% | 22.6% |

\* Among resolved loans only. Where a vintage is only partly resolved, this rate is **biased**: early defaults and early prepayments end first. That is why 2016 to 2017 look worse and 2018 looks better than they will end.

### 4.5 Realised net return and LGD (D-007)

- `total_pymnt` equals principal + interest + late fees + recoveries for every loan (largest gap: 1 cent).
- **Net realised return** per loan = `(total_pymnt - collection_recovery_fee - funded_amnt) / funded_amnt`. Median: +13.6% for good loans, -50.8% for bad loans. **D-007 is supported**, with two limitations: Lending Club's 1% investor service fee is not in the data, and there are no payment-by-payment dates, so only the total return (not an exact annualised one) can be computed.
- **LGD** = `(EAD - total_rec_prncp - (recoveries - collection_recovery_fee)) / EAD`, EAD = `funded_amnt`. Mean 0.634, median 0.676. 86 loans fall outside [0, 1] (recoveries above what was owed; minimum -1.17).
- **Recoveries keep arriving after charge-off**, and there is no recovery date. Share of bad loans with zero recoveries by charge-off year: about 1% up to 2013, 17% in 2015, 34% in 2018, 82% in 2019. So the LGD of recent charge-offs is overstated. Table: `lgd_by_chargeoff_year.csv`.
- How long recoveries take (table: `recovery_by_months_since_chargeoff.csv`), net recovery as a share of the funded amount by months since charge-off: 2.7% at 0 to 5 months, 6.0% at 6 to 11, 7.1% at 12 to 23, 6.6% to 7.4% at 24 to 35, 8.3% to 8.5% at 36 to 59, 5.8% at 60 or more. Most of it has arrived after 12 months. The oldest charge-offs are also from another collection era, which a single snapshot cannot separate from age. Basis for D-017.

## 5. Data quality

Table: `quality.json`. Counts are on the loans in scope (after D-013).

| Check | Result | Proposal (validated in F2) |
|---|---|---|
| Duplicate `id` | 0 | Uniqueness rule |
| Summary rows inside the file (two at the end of each original Lending Club file that Kaggle concatenated, plus one section title; corrected 2026-11-23, they are not only at the end) | 33 | Removed at ingestion |
| `member_id` | Empty in every row | Drop |
| `url` | Always `...loan_id=<id>`: no information | Drop |
| `term` | `" 36 months"`, `" 60 months"` (leading space) | Parse to 36 / 60 |
| `dti` | 2 negative, 135 equal to 999 (a code), 2,561 above 100, 1,711 missing | Negative and 999 to missing |
| `annual_inc` | 1,667 equal to 0; 3 above 10 million | Range rule; 0 checked against joint applications in F2 |
| `revol_util` | 7,316 above 100% (possible: balance over limit) | Keep, range rule up to a fixed maximum |
| `earliest_cr_line` | Parses for every row; none missing (the 29 missing were old-policy loans); never after the issue date | Parse to months of credit history at issue |
| `home_ownership` | MORTGAGE, RENT, OWN plus 1,189 loans as ANY, OTHER or NONE | Merge the last three |
| `emp_length` | Text (`"< 1 year"` to `"10+ years"`), 146,873 missing | Parse to 0 to 10 |
| Funded below requested | 1,924 loans | `loan_amnt` as feature, `funded_amnt` as EAD |
| `int_rate` | 5.31% to 30.99% | Range rule |
| `fico_range_low` | Minimum 625 | Range rule |

## 6. Simulation over time

### 6.1 Volumes

Lending Club grew from 251 loans in 2007 (after D-013) to 495,242 in 2018 (chart: `loans_per_month.png`, table: `loans_per_month.csv`).

| Year | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Loans | 251 | 1,562 | 4,716 | 11,536 | 21,721 | 53,367 | 134,814 | 235,629 | 421,095 | 434,407 | 443,579 | 495,242 |

### 6.2 Labels the system can use at a simulated date T

At date T the system may only use outcomes already known at T. Because the estimated resolution month is known for every resolved loan, and loans still running at the snapshot were running at every earlier date too, **label arrival can be replayed faithfully for any T up to the snapshot**.

Two possible rules for which known labels go into training:

- **Known by T**: every loan resolved by T. Biased: for recent vintages only the early endings are known, mostly defaults. The bad rate it shows is 17% to 20%, against 11% to 13% for complete cohorts.
- **Matured cohorts**: only loans issued at least `term + 5` months before T, whose outcome is fully known. Unbiased, but older and smaller.

| First training at T | Loans known by T | Their bad rate | Loans in matured cohorts | Their bad rate | Loans listed from T to 2018 |
|---|---|---|---|---|---|
| 2012-01 | 7,559 | 18.8% | 1,278 | 16.3% | 2,218,133 |
| 2013-01 | 18,951 | 17.5% | 4,335 | 13.8% | 2,164,766 |
| 2014-01 | 45,852 | 17.8% | 12,078 | 12.1% | 2,029,952 |
| 2015-01 | 113,208 | 17.4% | 23,358 | 11.0% | 1,794,323 |
| 2016-01 | 260,452 | 17.3% | 53,682 | 12.7% | 1,373,228 |
| 2017-01 | 502,116 | 19.0% | 139,593 | 13.1% | 938,821 |

Table: `labels_at_start_date.csv`.

### 6.3 Where the business metric can be measured

The business metric (D-007) needs the final outcome of every loan bought. At the snapshot that holds for 36-month loans listed up to 2015 (99.9% or more resolved) and for 60-month loans listed up to 2013. From 2016 on, outcomes are incomplete (section 4.4).

## 7. Indirect discrimination: `addr_state` and zip code

Neither field is a protected attribute, but both are classic proxies: where someone lives correlates with race and ethnicity, and using it to price or deny credit is the pattern known as redlining. Without demographic data the proxy effect cannot be measured directly, so the audit measures what they would add to the model.

| Check | Result |
|---|---|
| Cardinality | 51 states; 956 zip prefixes (3 digits), 447 of them with fewer than 1,000 loans |
| Bad rate by state (36-month loans issued up to 2015, states with 1,000+ loans) | From 9.2% (New Hampshire) to 18.7% (Mississippi). Table: `bad_rate_by_state.csv` |
| Value on top of `sub_grade` (logistic regression, train 36-month loans 2012 to 2014, out-of-time test on 2015) | AUC 0.6786 with `sub_grade` only; **+0.0021** adding state (95% bootstrap interval +0.0016 to +0.0028); **-0.0003** adding zip prefix (-0.0011 to +0.0005) |

Reading: the state adds a real but very small amount, below the 0.003 noise level of the AUC measured in the research phase. The zip prefix adds nothing. The legal and reputational risk of using them is large compared with that gain.

## 8. Errors found during the audit and how they were solved

Moved on 2026-11-22 to the project's error log (D-034): [E-001 to E-007 in `errors.md`](errors.md), now with how each one is prevented. Re-running this notebook in F1 found two more (E-010, E-011), fixed without changing any number.

## 9. Decisions for Juan

| # | Decision | Options | Recommendation | Why |
|---|---|---|---|---|
| 9.1 | Status mapping | **Decided (D-013)**: as in 4.1, but the "does not meet the credit policy" loans are removed | | |
| 9.2 | Columns dropped | **Decided (D-014, D-015)**: only fields proven in Browse Notes; `mths_since_recent_bc_dlq` dropped; free text not used in v1 | | |
| 9.3 | Fields that start in 2012, 2015 or 2017 | **Decided (D-016)**: option (a); entry rule set with the retraining policy | | |
| 9.4 | Training label rule (**deferred** to the simulation design) | Matured cohorts; known by T | **Matured cohorts** | Known by T inflates the bad rate from about 12% to 18%; the model would learn a biased level, and the PD must be calibrated for EL |
| 9.5 | Simulation window (**deferred** to the simulation design) | First training 2014-01, replay 2014 to 2018; first training 2015-01; first training 2016-01 | **First training 2014-01, replay 2014-01 to 2018-12** | 2 million loans replayed and five years of monitoring and retraining. First model: 12,078 matured loans (about 1,460 defaults, after D-013 removed 2,230 old-policy loans), weak but realistic. Business metric final for 36-month loans listed 2014 to 2015 (445,743 loans); from 2016 it is reported as "observed so far" |
| 9.6 | Time-based split of the first model (**deferred** to the simulation design) | Train on matured cohorts except their last 6 issue months, validate on those 6 months, real test = the forward replay; or random split | **Out-of-time as described** | A random split mixes vintages and hides drift |
| 9.7 | LGD labels | **Decided (D-017)**: only loans charged off at least 12 months before the training date | | |
| 9.8 | `addr_state` and zip code | **Decided (D-018)**: neither is a feature; `addr_state` kept for fairness monitoring | | |

Decided items are recorded in `decisions.md` (D-013 to D-018). When 9.4 to 9.6 are decided, `problem.md` section 7 is updated too (it says "matured or closed"; decision 9.4 refines it).

## Appendix: full data dictionary

Generated by the notebook (`reports/data_audit/data_dictionary.md`). `first_year_reported`: first issue year in which at least 1% of loans have a value. Empty: never reaches 1% in any year.

| column | meaning | type | pct_missing | first_year_reported | available_at_listing | use |
|---|---|---|---|---|---|---|
| id | A unique LC assigned ID for the loan listing. | String | 0.0 | 2007 | yes | identifier |
| member_id | A unique LC assigned Id for the borrower member. | String | 100.0 |  | yes | identifier |
| loan_amnt | The listed amount of the loan applied for by the borrower. If at some point in time, the credit department reduces the loan amount, then it will be reflected in this value. | Float64 | 0.0 | 2007 | yes | feature candidate |
| funded_amnt | The total amount committed to that loan at that point in time. | Float64 | 0.0 | 2007 | doubtful | target source (EAD) |
| funded_amnt_inv | The total amount committed by investors for that loan at that point in time. | Float64 | 0.0 | 2007 | no | drop (leakage) |
| term | The number of payments on the loan. Values are in months and can be either 36 or 60. | String | 0.0 | 2007 | yes | feature candidate |
| int_rate | Interest Rate on the loan | Float64 | 0.0 | 2007 | yes | feature candidate |
| installment | The monthly payment owed by the borrower if the loan originates. | Float64 | 0.0 | 2007 | yes | feature candidate |
| grade | LC assigned loan grade | String | 0.0 | 2007 | yes | feature candidate |
| sub_grade | LC assigned loan subgrade | String | 0.0 | 2007 | yes | feature candidate |
| emp_title | The job title supplied by the Borrower when applying for the loan.* | String | 7.4 | 2007 | yes | free text, not used in v1 |
| emp_length | Employment length in years. Possible values are between 0 and 10 where 0 means less than one year and 10 means ten or more years. | String | 6.5 | 2007 | yes | feature candidate |
| home_ownership | The home ownership status provided by the borrower during registration'or obtained from the credit report.'Our values are: RENT, OWN, MORTGAGE, OTHER | String | 0.0 | 2007 | yes | feature candidate |
| annual_inc | The self-reported annual income provided by the borrower during registration. | Float64 | 0.0 | 2007 | yes | feature candidate |
| verification_status | Indicates if income was verified by LC, not verified, or if the income source was verified | String | 0.0 | 2007 | yes | feature candidate |
| issue_d | The month which the loan was funded | String | 0.0 | 2007 | doubtful | decision |
| loan_status | Current status of the loan | String | 0.0 | 2007 | no | target source |
| pymnt_plan | Indicates if a payment plan has been put in place for the loan | String | 0.0 | 2007 | no | drop (leakage) |
| url | URL for the LC page with listing data. | String | 0.0 | 2007 | yes | identifier |
| desc | Loan description provided by the borrower | String | 94.4 | 2007 | yes | free text, not used in v1 |
| purpose | A category provided by the borrower for the loan request. | String | 0.0 | 2007 | yes | feature candidate |
| title | The loan title provided by the borrower | String | 1.0 | 2007 | yes | free text, not used in v1 |
| zip_code | The first 3 numbers of the zip code provided by the borrower in the loan application. | String | 0.0 | 2007 | yes | proxy review |
| addr_state | The state provided by the borrower in the loan application | String | 0.0 | 2007 | yes | proxy review |
| dti | A ratio calculated using the borrower's total monthly debt payments on the total debt obligations, excluding mortgage and the requested LC loan, divided by the borrower's self-reported monthly income. | Float64 | 0.1 | 2007 | yes | feature candidate |
| delinq_2yrs | The number of 30+ days past-due incidences of delinquency in the borrower's credit file for the past 2 years | Float64 | 0.0 | 2007 | yes | feature candidate |
| earliest_cr_line | The month the borrower's earliest reported credit line was opened | String | 0.0 | 2007 | yes | feature candidate |
| fico_range_low | The lower boundary range the borrower's FICO at loan origination belongs to. | Float64 | 0.0 | 2007 | yes | feature candidate |
| fico_range_high | The upper boundary range the borrower's FICO at loan origination belongs to. | Float64 | 0.0 | 2007 | yes | feature candidate |
| inq_last_6mths | The number of inquiries in past 6 months (excluding auto and mortgage inquiries) | Float64 | 0.0 | 2007 | yes | feature candidate |
| mths_since_last_delinq | The number of months since the borrower's last delinquency. | Float64 | 51.2 | 2007 | yes | feature candidate |
| mths_since_last_record | The number of months since the last public record. | Float64 | 84.1 | 2007 | yes | feature candidate |
| open_acc | The number of open credit lines in the borrower's credit file. | Float64 | 0.0 | 2007 | yes | feature candidate |
| pub_rec | Number of derogatory public records | Float64 | 0.0 | 2007 | yes | feature candidate |
| revol_bal | Total credit revolving balance | Float64 | 0.0 | 2007 | yes | feature candidate |
| revol_util | Revolving line utilization rate, or the amount of credit the borrower is using relative to all available revolving credit. | Float64 | 0.1 | 2007 | yes | feature candidate |
| total_acc | The total number of credit lines currently in the borrower's credit file | Float64 | 0.0 | 2007 | yes | feature candidate |
| initial_list_status | The initial listing status of the loan. Possible values are ' W, F | String | 0.0 | 2007 | yes | feature candidate |
| out_prncp | Remaining outstanding principal for total amount funded | Float64 | 0.0 | 2007 | no | drop (leakage) |
| out_prncp_inv | Remaining outstanding principal for portion of total amount funded by investors | Float64 | 0.0 | 2007 | no | drop (leakage) |
| total_pymnt | Payments received to date for total amount funded | Float64 | 0.0 | 2007 | no | target source |
| total_pymnt_inv | Payments received to date for portion of total amount funded by investors | Float64 | 0.0 | 2007 | no | drop (leakage) |
| total_rec_prncp | Principal received to date | Float64 | 0.0 | 2007 | no | target source |
| total_rec_int | Interest received to date | Float64 | 0.0 | 2007 | no | target source |
| total_rec_late_fee | Late fees received to date | Float64 | 0.0 | 2007 | no | target source |
| recoveries | post charge off gross recovery | Float64 | 0.0 | 2007 | no | target source |
| collection_recovery_fee | post charge off collection fee | Float64 | 0.0 | 2007 | no | target source |
| last_pymnt_d | Last month payment was received | String | 0.1 | 2007 | no | target source |
| last_pymnt_amnt | Last total payment amount received | Float64 | 0.0 | 2007 | no | drop (leakage) |
| next_pymnt_d | Next scheduled payment date | String | 59.5 | 2007 | no | drop (leakage) |
| last_credit_pull_d | The most recent month LC pulled credit for this loan | String | 0.0 | 2007 | no | drop (leakage) |
| last_fico_range_high | The upper boundary range the borrower's last FICO pulled belongs to. | Float64 | 0.0 | 2007 | no | drop (leakage) |
| last_fico_range_low | The lower boundary range the borrower's last FICO pulled belongs to. | Float64 | 0.0 | 2007 | no | drop (leakage) |
| collections_12_mths_ex_med | Number of collections in 12 months excluding medical collections | Float64 | 0.0 | 2007 | yes | feature candidate |
| mths_since_last_major_derog | Months since most recent 90-day or worse rating | Float64 | 74.3 | 2012 | yes | feature candidate |
| policy_code | publicly available policy_code=1 new products not publicly available policy_code=2 | Float64 | 0.0 | 2007 | no | drop (constant) |
| application_type | Indicates whether the loan is an individual application or a joint application with two co-borrowers | String | 0.0 | 2007 | yes | feature candidate |
| annual_inc_joint | The combined self-reported annual income provided by the co-borrowers during registration | Float64 | 94.7 | 2016 | yes | feature candidate |
| dti_joint | A ratio calculated using the co-borrowers' total monthly payments on the total debt obligations, excluding mortgages and the requested LC loan, divided by the co-borrowers' combined self-reported monthly income | Float64 | 94.7 | 2016 | yes | feature candidate |
| verification_status_joint | Indicates if the co-borrowers' joint income was verified by LC, not verified, or if the income source was verified | String | 94.9 | 2016 | yes | feature candidate |
| acc_now_delinq | The number of accounts on which the borrower is now delinquent. | Float64 | 0.0 | 2007 | yes | feature candidate |
| tot_coll_amt | Total collection amounts ever owed | Float64 | 3.1 | 2012 | yes | feature candidate |
| tot_cur_bal | Total current balance of all accounts | Float64 | 3.1 | 2012 | yes | feature candidate |
| open_acc_6m | Number of open trades in last 6 months | Float64 | 38.3 | 2015 | yes | feature candidate |
| open_act_il | Number of currently active installment trades | Float64 | 38.3 | 2015 | yes | feature candidate |
| open_il_12m | Number of installment accounts opened in past 12 months | Float64 | 38.3 | 2015 | yes | feature candidate |
| open_il_24m | Number of installment accounts opened in past 24 months | Float64 | 38.3 | 2015 | yes | feature candidate |
| mths_since_rcnt_il | Months since most recent installment accounts opened | Float64 | 40.3 | 2015 | yes | feature candidate |
| total_bal_il | Total current balance of all installment accounts | Float64 | 38.3 | 2015 | yes | feature candidate |
| il_util | Ratio of total current balance to high credit/credit limit on all install acct | Float64 | 47.3 | 2015 | yes | feature candidate |
| open_rv_12m | Number of revolving trades opened in past 12 months | Float64 | 38.3 | 2015 | yes | feature candidate |
| open_rv_24m | Number of revolving trades opened in past 24 months | Float64 | 38.3 | 2015 | yes | feature candidate |
| max_bal_bc | Maximum current balance owed on all revolving accounts | Float64 | 38.3 | 2015 | yes | feature candidate |
| all_util | Balance to credit limit on all trades | Float64 | 38.3 | 2015 | yes | feature candidate |
| total_rev_hi_lim | Total revolving high credit/credit limit | Float64 | 3.1 | 2012 | yes | feature candidate |
| inq_fi | Number of personal finance inquiries | Float64 | 38.3 | 2015 | yes | feature candidate |
| total_cu_tl | Number of finance trades | Float64 | 38.3 | 2015 | yes | feature candidate |
| inq_last_12m | Number of credit inquiries in past 12 months | Float64 | 38.3 | 2015 | yes | feature candidate |
| acc_open_past_24mths | Number of trades opened in past 24 months. | Float64 | 2.2 | 2012 | yes | feature candidate |
| avg_cur_bal | Average current balance of all accounts | Float64 | 3.1 | 2012 | yes | feature candidate |
| bc_open_to_buy | Total open to buy on revolving bankcards. | Float64 | 3.3 | 2012 | yes | feature candidate |
| bc_util | Ratio of total current balance to high credit/credit limit for all bankcard accounts. | Float64 | 3.4 | 2012 | yes | feature candidate |
| chargeoff_within_12_mths | Number of charge-offs within 12 months | Float64 | 0.0 | 2007 | yes | feature candidate |
| delinq_amnt | The past-due amount owed for the accounts on which the borrower is now delinquent. | Float64 | 0.0 | 2007 | yes | feature candidate |
| mo_sin_old_il_acct | Months since oldest bank installment account opened | Float64 | 6.2 | 2012 | yes | feature candidate |
| mo_sin_old_rev_tl_op | Months since oldest revolving account opened | Float64 | 3.1 | 2012 | yes | feature candidate |
| mo_sin_rcnt_rev_tl_op | Months since most recent revolving account opened | Float64 | 3.1 | 2012 | yes | feature candidate |
| mo_sin_rcnt_tl | Months since most recent account opened | Float64 | 3.1 | 2012 | yes | feature candidate |
| mort_acc | Number of mortgage accounts. | Float64 | 2.2 | 2012 | yes | feature candidate |
| mths_since_recent_bc | Months since most recent bankcard account opened. | Float64 | 3.2 | 2012 | yes | feature candidate |
| mths_since_recent_bc_dlq | Months since most recent bankcard delinquency | Float64 | 77.0 | 2012 | doubtful | decision |
| mths_since_recent_inq | Months since most recent inquiry. | Float64 | 13.1 | 2012 | yes | feature candidate |
| mths_since_recent_revol_delinq | Months since most recent revolving delinquency. | Float64 | 67.3 | 2012 | yes | feature candidate |
| num_accts_ever_120_pd | Number of accounts ever 120 or more days past due | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_actv_bc_tl | Number of currently active bankcard accounts | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_actv_rev_tl | Number of currently active revolving trades | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_bc_sats | Number of satisfactory bankcard accounts | Float64 | 2.6 | 2012 | yes | feature candidate |
| num_bc_tl | Number of bankcard accounts | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_il_tl | Number of installment accounts | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_op_rev_tl | Number of open revolving accounts | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_rev_accts | Number of revolving accounts | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_rev_tl_bal_gt_0 | Number of revolving trades with balance >0 | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_sats | Number of satisfactory accounts | Float64 | 2.6 | 2012 | yes | feature candidate |
| num_tl_120dpd_2m | Number of accounts currently 120 days past due (updated in past 2 months) | Float64 | 6.8 | 2012 | yes | feature candidate |
| num_tl_30dpd | Number of accounts currently 30 days past due (updated in past 2 months) | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_tl_90g_dpd_24m | Number of accounts 90 or more days past due in last 24 months | Float64 | 3.1 | 2012 | yes | feature candidate |
| num_tl_op_past_12m | Number of accounts opened in past 12 months | Float64 | 3.1 | 2012 | yes | feature candidate |
| pct_tl_nvr_dlq | Percent of trades never delinquent | Float64 | 3.1 | 2012 | yes | feature candidate |
| percent_bc_gt_75 | Percentage of all bankcard accounts > 75% of limit. | Float64 | 3.3 | 2012 | yes | feature candidate |
| pub_rec_bankruptcies | Number of public record bankruptcies | Float64 | 0.1 | 2007 | yes | feature candidate |
| tax_liens | Number of tax liens | Float64 | 0.0 | 2007 | yes | feature candidate |
| tot_hi_cred_lim | Total high credit/credit limit | Float64 | 3.1 | 2012 | yes | feature candidate |
| total_bal_ex_mort | Total credit balance excluding mortgage | Float64 | 2.2 | 2012 | yes | feature candidate |
| total_bc_limit | Total bankcard high credit/credit limit | Float64 | 2.2 | 2012 | yes | feature candidate |
| total_il_high_credit_limit | Total installment high credit/credit limit | Float64 | 3.1 | 2012 | yes | feature candidate |
| revol_bal_joint | Sum of revolving credit balance of the co-borrowers, net of duplicate balances | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_fico_range_low | FICO range (high) for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_fico_range_high | FICO range (low) for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_earliest_cr_line | Earliest credit line at time of application for the secondary applicant | String | 95.2 | 2017 | yes | feature candidate |
| sec_app_inq_last_6mths | Credit inquiries in the last 6 months at time of application for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_mort_acc | Number of mortgage accounts at time of application for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_open_acc | Number of open trades at time of application for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_revol_util | Ratio of total current balance to high credit/credit limit for all revolving accounts | Float64 | 95.3 | 2017 | yes | feature candidate |
| sec_app_open_act_il | Number of currently active installment trades at time of application for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_num_rev_accts | Number of revolving accounts at time of application for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_chargeoff_within_12_mths | Number of charge-offs within last 12 months at time of application for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_collections_12_mths_ex_med | Number of collections within last 12 months excluding medical collections at time of application for the secondary applicant | Float64 | 95.2 | 2017 | yes | feature candidate |
| sec_app_mths_since_last_major_derog | Months since most recent 90-day or worse rating at time of application for the secondary applicant | Float64 | 98.4 | 2017 | yes | feature candidate |
| hardship_flag | Flags whether or not the borrower is on a hardship plan | String | 0.0 | 2007 | no | drop (leakage) |
| hardship_type | Describes the hardship plan offering | String | 99.5 | 2016 | no | drop (leakage) |
| hardship_reason | Describes the reason the hardship plan was offered | String | 99.5 | 2016 | no | drop (leakage) |
| hardship_status | Describes if the hardship plan is active, pending, canceled, completed, or broken | String | 99.5 | 2016 | no | drop (leakage) |
| deferral_term | Amount of months that the borrower is expected to pay less than the contractual monthly payment amount due to a hardship plan | Float64 | 99.5 | 2016 | no | drop (leakage) |
| hardship_amount | The interest payment that the borrower has committed to make each month while they are on a hardship plan | Float64 | 99.5 | 2016 | no | drop (leakage) |
| hardship_start_date | The start date of the hardship plan period | String | 99.5 | 2016 | no | drop (leakage) |
| hardship_end_date | The end date of the hardship plan period | String | 99.5 | 2016 | no | drop (leakage) |
| payment_plan_start_date | The day the first hardship plan payment is due. For example, if a borrower has a hardship plan period of 3 months, the start date is the start of the three-month period in which the borrower is allowed to make interest-only payments. | String | 99.5 | 2016 | no | drop (leakage) |
| hardship_length | The number of months the borrower will make smaller payments than normally obligated due to a hardship plan | Float64 | 99.5 | 2016 | no | drop (leakage) |
| hardship_dpd | Account days past due as of the hardship plan start date | Float64 | 99.5 | 2016 | no | drop (leakage) |
| hardship_loan_status | Loan Status as of the hardship plan start date | String | 99.5 | 2016 | no | drop (leakage) |
| orig_projected_additional_accrued_interest | The original projected additional interest amount that will accrue for the given hardship payment plan as of the Hardship Start Date. This field will be null if the borrower has broken their hardship payment plan. | Float64 | 99.6 |  | no | drop (leakage) |
| hardship_payoff_balance_amount | The payoff balance amount as of the hardship plan start date | Float64 | 99.5 | 2016 | no | drop (leakage) |
| hardship_last_payment_amount | The last payment amount as of the hardship plan start date | Float64 | 99.5 | 2016 | no | drop (leakage) |
| disbursement_method | The method by which the borrower receives their loan. Possible values are: CASH, DIRECT_PAY | String | 0.0 | 2007 | yes | feature candidate |
| debt_settlement_flag | Flags whether or not the borrower, who has charged-off, is working with a debt-settlement company. | String | 0.0 | 2007 | no | drop (leakage) |
| debt_settlement_flag_date | The most recent date that the Debt_Settlement_Flag has been set'' | String | 98.5 | 2013 | no | drop (leakage) |
| settlement_status | The status of the borrower's settlement plan. Possible values are: COMPLETE, ACTIVE, BROKEN, CANCELLED, DENIED, DRAFT | String | 98.5 | 2013 | no | drop (leakage) |
| settlement_date | The date that the borrower agrees to the settlement plan | String | 98.5 | 2013 | no | drop (leakage) |
| settlement_amount | The loan amount that the borrower has agreed to settle for | Float64 | 98.5 | 2013 | no | drop (leakage) |
| settlement_percentage | The settlement amount as a percentage of the payoff balance amount on the loan | Float64 | 98.5 | 2013 | no | drop (leakage) |
| settlement_term | The number of months that the borrower will be on the settlement plan | Float64 | 98.5 | 2013 | no | drop (leakage) |
