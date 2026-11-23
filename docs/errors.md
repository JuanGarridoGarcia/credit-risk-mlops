# Error log

Every error found while building the project: what was seen, why it happened, how it was fixed and what stops it from happening again. Format decided in D-034.

The question for each entry is not "who did it" but "what was missing in the system for this to happen" (blameless postmortem). **Prevention** is, whenever possible, an automatic test or check; "be careful" does not scale. When no automatic prevention is possible, the entry says why.

## Index

| ID | Date | Step | Error | Severity |
|---|---|---|---|---|
| [E-001](#e-001) | 2026-11-21 | 0.2 | Session could not see the Kaggle token | Blocking |
| [E-002](#e-002) | 2026-11-21 | 0.2 | Kaggle CLI blocked by the network allowlist | Blocking |
| [E-003](#e-003) | 2026-11-21 | 0.2 | Main dataset has no data dictionary | Major |
| [E-004](#e-004) | 2026-11-21 | 0.2 | 33 summary rows inside the loan data | Major |
| [E-005](#e-005) | 2026-11-21 | 0.2 | Audit notebook ran out of memory | Blocking |
| [E-006](#e-006) | 2026-11-21 | 0.2 | Month-only dates did not parse | Minor |
| [E-007](#e-007) | 2026-11-21 | 0.2 | Estimated charge-off dates after the snapshot | Minor |
| [E-008](#e-008) | 2026-11-22 | 1.2 | `docker build` could not download anything in the cloud machine | Blocking (local only) |
| [E-009](#e-009) | 2026-11-22 | 1.2 | Postgres 18 moved its data directory (caught before it happened) | Major |
| [E-010](#e-010) | 2026-11-22 | 1.1 | Audit outputs changed row order between runs | Minor |
| [E-011](#e-011) | 2026-11-22 | 1.1 | Audit notebook deleted a variable a function still reads | Minor |
| [E-012](#e-012) | 2026-11-22 | 1.2 | Image test could not search the whole file system | Minor |
| [E-013](#e-013) | 2026-11-23 | 2.1 | Audit text and notebook disagreed on the charge-off month by one month | Minor |
| [E-014](#e-014) | 2026-11-23 | 2.1 | `dti = 999` proposed as "unknown" without looking at the income of those rows | Minor |
| [E-015](#e-015) | 2026-11-23 | 2.1 | Publishing every delivery took almost 6 minutes | Minor |
| [E-016](#e-016) | 2026-11-23 | 2.1 | Splitting the whole snapshot by month at once ran out of memory | Minor |
| [E-017](#e-017) | 2026-11-23 | 2.1 | The data tests folder was ignored by git | Minor |
| [E-018](#e-018) | 2026-11-23 | 2.1 | polars reads a row with too few fields as nulls instead of failing | Major |
| [E-019](#e-019) | 2026-11-23 | 2.1 | Column `desc` is a reserved word in SQL | Minor |
| [E-020](#e-020) | 2026-11-23 | 2.2 | Required columns taken from the whole file, not from the past | Major |
| [E-021](#e-021) | 2026-11-23 | 2.2 | Catalogue months of R2.13 written from a guess, not measured | Minor |
| [E-022](#e-022) | 2026-11-23 | 2.3 | First training set counted with outcomes known only after T0 | Minor |
| [E-023](#e-023) | 2026-11-23 | 2.4 | Notebooks workflow failed deep in the notebook when the Kaggle secret was missing | Minor |
| [E-024](#e-024) | 2026-11-23 | 2.4 | The audit figure came out with different bytes on GitHub | Minor |

## Errors

<a id="e-001"></a>
### E-001 Session could not see the Kaggle token

Date: 2026-11-21 · Step: 0.2 · Severity: blocking

- **Symptom**: the first F0 session could not find `KAGGLE_API_TOKEN`.
- **Cause**: environment variables are read when the cloud machine starts; the token was added afterwards.
- **Fix**: a new session for step 0.2.
- **Prevention**: secrets are configured before a thread starts (recorded in the working rules). No automatic check is possible from inside the project.

<a id="e-002"></a>
### E-002 Kaggle CLI blocked by the network allowlist

Date: 2026-11-21 · Step: 0.2 · Severity: blocking

- **Symptom**: `kaggle` CLI failed with a proxy 403 on `api.kaggle.com`.
- **Cause**: the new CLI (2.x, needed for the new token format) talks to `api.kaggle.com`, which was not in the network allowlist (only `kaggle.com`, `www.kaggle.com`, `storage.googleapis.com`).
- **Fix**: `api.kaggle.com` added to the environment allowlist (approved by Juan).
- **Prevention**: the automated download step of F2 (step 2.1) fails fast with a clear message naming the host it could not reach.

<a id="e-003"></a>
### E-003 Main dataset has no data dictionary

Date: 2026-11-21 · Step: 0.2 · Severity: major

- **Symptom**: the main Kaggle dataset ships without column descriptions.
- **Cause**: the uploader could not upload Lending Club's .xlsx dictionary.
- **Fix**: a second Kaggle dataset with the official dictionary, used as documentation only, with its hash recorded.
- **Prevention**: the dictionary file is pinned by SHA-256 like the data (D-012); a changed file stops the audit.

<a id="e-004"></a>
### E-004 33 summary rows inside the loan data

Date: 2026-11-21 · Step: 0.2 · Severity: major

- **Symptom**: 33 rows with text in `id` and nulls elsewhere.
- **Cause**: summary rows that Lending Club appended to its exports.
- **Fix**: detected by missing `loan_amnt` and removed.
- **Prevention**: a data validation rule in F2 (step 2.2) rejects rows without `loan_amnt` or with a non-numeric `id`, and reports how many were removed.

<a id="e-005"></a>
### E-005 Audit notebook ran out of memory

Date: 2026-11-21 · Step: 0.2 · Severity: blocking

- **Symptom**: the notebook was killed at 14 GB of memory.
- **Cause**: the full 151-column table was copied several times by filters.
- **Fix**: load once and keep only the needed columns after the dictionary step. Peak now 9.8 GB.
- **Prevention**: the F2 pipeline reads only the columns it needs (column selection at load time); a memory budget for the pipeline is set in F2.

<a id="e-006"></a>
### E-006 Month-only dates did not parse

Date: 2026-11-21 · Step: 0.2 · Severity: minor

- **Symptom**: dates such as `Dec-2015` did not parse.
- **Cause**: the parser needs a day.
- **Fix**: prefix `01-` and parse as the first day of the month.
- **Prevention**: a unit test of the date parser in F2, with this format among its cases.

<a id="e-007"></a>
### E-007 Estimated charge-off dates after the snapshot

Date: 2026-11-21 · Step: 0.2 · Severity: minor

- **Symptom**: some charged-off loans had an estimated charge-off date after the data snapshot.
- **Cause**: the 5-month charge-off lag is typical, not fixed.
- **Fix**: estimate capped at the snapshot.
- **Prevention**: a data validation rule in F2: no event date later than the snapshot date.

<a id="e-008"></a>
### E-008 `docker build` could not download anything in the cloud machine

Date: 2026-11-22 · Step: 1.2 · Severity: blocking, only in Claude's cloud machine (not in CI, not on a normal PC)

- **Symptom**: pulling `ghcr.io/astral-sh/uv` failed (DNS error on `pkg-containers.githubusercontent.com`), and steps inside the build could not reach PyPI.
- **Cause**: the cloud machine reaches the internet only through a proxy that inspects TLS with its own certificate authority. Containers do not see the proxy and do not trust its certificate; the GitHub container registry's download host was not reachable at all.
- **Fix**: uv is taken from the same image published on Docker Hub (`astral/uv`, pinned by digest). Builds in the cloud machine run with `--network host`, the proxy as a build argument (Docker never stores proxy arguments in the image history), and the proxy certificate as a BuildKit **secret**, which is mounted only while a step runs and never written into a layer. The Dockerfile uses it only if present; elsewhere the build is unchanged. The flags go in `DOCKER_BUILD_FLAGS` (see the Makefile).
- **Prevention**: test B5 checks that no proxy, password or token appears in the image configuration or history.

<a id="e-009"></a>
### E-009 Postgres 18 moved its data directory (caught before it happened)

Date: 2026-11-22 · Step: 1.2 · Severity: major (it would lose every stored prediction)

- **Symptom (avoided)**: with the volume mounted on `/var/lib/postgresql/data`, as in most tutorials for earlier versions, Postgres 18 would start and work normally but write its data inside the container, losing it whenever the container is recreated.
- **Cause**: the official Postgres 18 image stores data in `/var/lib/postgresql/18/docker` (checked: `PGDATA` in the image).
- **Fix**: the volume is mounted on `/var/lib/postgresql`.
- **Prevention**: test B4 writes a random value, destroys and recreates the container, and checks the value is still there.

<a id="e-010"></a>
### E-010 Audit outputs changed row order between runs

Date: 2026-11-22 · Step: 1.1 · Severity: minor

- **Symptom**: re-running the audit notebook with the new uv environment (D-024) changed three output files (`bad_rate_by_state.csv`, `loans_per_month.csv`, `quality.json`).
- **Cause**: only the order of rows changed, never a number: polars does not guarantee the order of `group_by` and `unique`, and a sort on one column leaves ties in any order.
- **Fix**: every output is now fully sorted (ties broken by a second column; lists and dictionaries sorted). Re-ran the notebook twice: both runs byte-identical, and every value identical to F0.
- **Prevention**: in F2, pipeline outputs are written with an explicit total order, and a test runs a step twice and compares the outputs.

<a id="e-011"></a>
### E-011 Audit notebook deleted a variable a function still reads

Date: 2026-11-22 · Step: 1.1 · Severity: minor (latent, never triggered)

- **Symptom**: ruff reported `by_year` as undefined in `first_year()` (rule F821) the first time it checked the notebook.
- **Cause**: a later cell ran `del fico, by_year` to free memory, but `first_year()` reads `by_year`. Calling it after that cell would have failed.
- **Fix**: `by_year` (a small table) is no longer deleted.
- **Prevention**: ruff now checks notebooks in pre-commit and CI.

<a id="e-012"></a>
### E-012 Image test could not search the whole file system

Date: 2026-11-22 · Step: 1.2 · Severity: minor

- **Symptom**: the first version of `test_image_has_no_env_file` failed with "Permission denied".
- **Cause**: the image runs as an unprivileged user (D-025), which cannot read some system folders, so `find` exited with an error.
- **Fix**: the test inspects the image as root (`--user 0`), only to look; the image itself still runs unprivileged, which `test_image_runs_as_non_root` checks.
- **Prevention**: the test itself; recorded so the reason for `--user 0` is clear.

<a id="e-013"></a>
### E-013 Audit text and notebook disagreed on the charge-off month by one month

Date: 2026-11-23 · Step: 2.1 · Severity: minor

- **Symptom**: while specifying the simulator's resolution month, `data_audit.md` section 4.2 described the charge-off month as "5 months after the first missed payment" (`last_pymnt_d` + 6), while the notebook computes `last_pymnt_d` + 5 (and issue + 5 for loans that never paid, which the text called "issue + 1").
- **Cause**: the text was written from Lending Club's 150-day rule, the code from the data; nothing compared them.
- **Fix**: checked against the data on 2026-11-23, using the months between the last payment and the snapshot (2019-03) for loans still open: "In Grace Period" 0 to 1 months, "Late (16-30 days)" mostly 1, "Late (31-120 days)" 2 to 4 (3,938 loans at 4, only 17 at 5), "Default" (121+ days, not yet charged off) only 40 loans. Loans leave the late states at about 5 months after the last payment, so `last_pymnt_d` + 5 is the supported rule. Text corrected; numbers in the audit and in D-040 to D-042 were computed with the notebook's rule and do not change.
- **Prevention**: the rule is implemented once, in the simulator, with unit tests that state it explicitly; the documentation points to that code.

<a id="e-014"></a>
### E-014 `dti = 999` proposed as "unknown" without looking at the income of those rows

Date: 2026-11-23 · Step: 2.1 · Severity: minor (caught before any code was written)

- **Symptom**: the audit (section 5) proposed turning `dti = 999` into missing, and Claude repeated it as the example of a cleaning rule. Checking `annual_inc = 0` at Juan's suggestion (look at related columns) showed that the 135 loans with `dti = 999` have annual incomes of only 15 to 3,600 dollars: 999 is a cap on an enormous ratio caused by an implausible income, not a code for "unknown".
- **Cause**: the proposal was based on the value alone, without checking the columns it is computed from.
- **Fix**: under the cleaning boundary (D-051), cleaning keeps `dti = 999` and `dti = -1` as they are; validation flags them and feature engineering (step 2.4) decides. The same check showed that all 1,667 loans with `annual_inc = 0` are joint applications with `annual_inc_joint` filled and, in 1,659 of them, `dti` empty (division by zero income): a real value, not a code.
- **Prevention**: a value is treated as a code only if Lending Club's documentation says so; otherwise it is a validation rule. Every rule about a derived column is checked against the columns it is derived from.

<a id="e-015"></a>
### E-015 Publishing every delivery took almost 6 minutes

Date: 2026-11-23 · Step: 2.1 · Severity: minor

- **Symptom**: the first version of the simulator took 5 min 40 s to publish the 284 deliveries (2007-06 to 2019-03).
- **Cause**: Python's `gzip` compresses at level 9 by default. Measured on the largest month (2016-03, 36.5 MB of CSV): level 9 takes 10 s for 8.4 MB, level 6 takes 1.1 s for 8.8 MB.
- **Fix**: level 6 (`GZIP_LEVEL` in `simulator/io.py`). Full publication: 60 s.
- **Prevention**: measure before optimising; the measurement is recorded next to the constant.

<a id="e-016"></a>
### E-016 Splitting the whole snapshot by month at once ran out of memory

Date: 2026-11-23 · Step: 2.1 · Severity: minor

- **Symptom**: a version that split the prepared snapshot into all monthly deliveries in one `group_by` was killed by the kernel for lack of memory (15 GB machine).
- **Cause**: it held the full table (2.26 million rows, 151 text columns) plus a copy split into 284 pieces.
- **Fix**: the prepared snapshot is cached as Parquet and read lazily; each delivery reads only its month.
- **Prevention**: the data test (T1.12) publishes the full file on every run of `make test-data`, so a change that brings the problem back is seen at once.

<a id="e-017"></a>
### E-017 The data tests folder was ignored by git

Date: 2026-11-23 · Step: 2.1 · Severity: minor (caught before pushing)

- **Symptom**: after committing the simulator, `tests/data/` was missing from the commit.
- **Cause**: `.gitignore` had `data/`, which matches a folder called `data` at any depth, not only the top-level data folder.
- **Fix**: `/data/` (anchored to the repository root).
- **Prevention**: `git status` is checked after every commit for files that should be there; the anchored pattern makes the intent explicit.

<a id="e-018"></a>
### E-018 polars reads a row with too few fields as nulls instead of failing

Date: 2026-11-23 · Step: 2.1 · Severity: major (caught by test T3.5 before any real load)

- **Symptom**: test T3.5 appends a truncated row (`4,this row has too few fields`) to a delivery and expects the load to fail. It loaded: polars `read_csv` filled the missing 107 fields with nulls. A row with too many fields does fail.
- **Cause**: lenient default of polars for short rows; there is no option to make it strict.
- **Fix**: ingestion reads deliveries with `read_delivery` (standard `csv` module, `strict=True`): the header must equal the contract and every record must have exactly that many fields, or the load stops naming the record. The rest of the pipeline keeps polars.
- **Prevention**: test T3.5 (now expects `DeliveryError`, "record 5 has 2 fields"). Lesson: "fail fast" must be checked, not assumed, for every library at a boundary.

<a id="e-019"></a>
### E-019 Column `desc` is a reserved word in SQL

Date: 2026-11-23 · Step: 2.1 · Severity: minor

- **Symptom**: the raw-tables migration failed with `syntax error at or near "desc"`.
- **Cause**: `desc` (the loan description) is a reserved word (`ORDER BY ... DESC`).
- **Fix**: quoted as `"desc"` in the migrations. Python code composes every name with `psycopg.sql.Identifier`, which always quotes, so it was not affected. dbmate runs each migration in a transaction, so the failed one left nothing behind.
- **Prevention**: test T3.1 applies every migration on an empty database in CI.

<a id="e-020"></a>
### E-020 Required columns taken from the whole file, not from the past

Date: 2026-11-23 · Step: 2.2 · Severity: major (caught before implementation)

- **Symptom**: the first version of rules R4.1 and R4.2 (approved as group 4) listed the columns that "never came empty", measured on 2007 to 2018. A team at 2013-12 could not have known that: 4 columns complete through 2013 get empty values later (`num_rev_accts` 2015-10, `inq_last_6mths` 2016-01, `zip_code` 2017-01, one row each; `last_credit_pull_d` from 2014-08, 53 sporadic rows).
- **Cause**: the same mistake Juan had caught for allowed values (D-056, option B): using knowledge of the file's future to define the contract.
- **Fix**: found while implementing, before any code was merged, and approved by Juan: required columns come only from the history up to 2013-12 (complete through 2013, required from the month after their last gap); the 3 single rows became reviewed exceptions and `last_credit_pull_d` the dated change C9.
- **Prevention**: test T4.16 runs the base contract alone over every real delivery and checks that it stops exactly at the months of the recorded changes, so a rule built from future data shows up as an unexplained stop. Every threshold chosen from data now says which months it was measured on.

<a id="e-021"></a>
### E-021 Catalogue months of R2.13 written from a guess, not measured

Date: 2026-11-23 · Step: 2.2 · Severity: minor

- **Symptom**: the catalogue said R2.13 (rate above every rate seen) fires in 2015 at 28.99% and in 2016 at 30.99%. The full load showed 2015-05 (26.77%), 2016-04 (29.96%) and 2016-05 (30.99%), plus 18 months of the history as rates rose.
- **Cause**: the months were inferred from the yearly maximum rates instead of being measured with the rule itself.
- **Fix**: catalogue corrected with the measured months.
- **Prevention**: test T4.15 checks every number of the catalogue against the full real load, so a number written from a guess fails.

### E-022 First training set counted with outcomes known only after T0

Date: 2026-11-23 · Step: 2.3 · Severity: minor

- **Symptom**: test T5.13 expected the counts of the audit and of D-041/D-042 at T0 = 2014-01: 12,078 matured loans, train 7,745, validation 4,333 with 432 defaults, 2,230 old-policy loans. The version built from clean at T0 has 12,057: train 7,733 (1,019 defaults), validation 4,324 (429 defaults), 2,226 old-policy loans and 25 matured loans with no outcome yet.
- **Cause**: the audit counted matured loans with their final status in the 2019-03 snapshot. 25 of them were resolved after T0, between 2014-02 and 2016-01 (21 of the current policy, 9 of them defaults; 4 of the old policy), so at T0 nobody could know their label. The same mistake as E-020: a figure computed with knowledge of the file's future.
- **Fix**: T5.13 (approved by Juan) checks the counts known at T0 and reconciles them with the audit: the 21 and 4 loans are found in the later deliveries and added back give 12,078 and 2,230. The decisions keep their text; the numbers of the first model are those of technical.md, step 2.3. The difference does not change D-041 (still enough defaults for the first model).
- **Prevention**: every count of a training set comes from a version built at its cutoff (T5.13, T5.14), never from the whole file.

### E-023 Notebooks workflow failed deep in the notebook when the Kaggle secret was missing

Date: 2026-11-23 · Step: 2.4 · Severity: minor

- **Symptom**: the first run of the Notebooks workflow (D-065), on PR #5, failed in cell 3 of the audit notebook with `CalledProcessError` from `kaggle datasets metadata`. The log does not say why.
- **Cause**: the repository secret `KAGGLE_API_TOKEN` was not created yet, so the job ran with an empty token. Nothing checked it before the notebook started.
- **Fix**: a first step in the workflow stops the job with a clear error when the secret is empty. The secret is added by the repository owner in the GitHub settings.
- **Prevention**: the same check stops every later run at the first step with the message, so a missing or deleted secret is seen at once.

### E-024 The audit figure came out different on GitHub

Date: 2026-11-23 · Step: 2.4 · Severity: minor

- **Symptom**: the first full run of the Notebooks workflow (D-065) on GitHub executed the notebook without error and every table matched, but `reports/data_audit/loans_per_month.png` changed from 58,213 to 49,354 bytes. Decoded, 38,719 pixels differed, spread over the whole plot. In the cloud machine where it was made, the same run gave the same bytes.
- **Cause**: the figure is drawn from `loans_per_month.csv`, which matched byte for byte, with the same locked library versions, so the drawing itself depends on the machine. Ruled out here: the font (the system copy of DejaVu Sans gives the same image), the CPU paths of numpy and OpenBLAS (turning off AVX-512 gives the same image) and the PNG compression (a first fix compared pixels instead of bytes and still failed). The exact cause was not found, because the artifact with the GitHub image cannot be downloaded from the cloud machine.
- **Fix**: Juan decided to leave the PNG figures out of the comparison: `git diff --exit-code -- reports/data_audit ':(exclude)*.png'`. A figure is a view of a table that is still compared, so a changed number is still caught. A failed run uploads its outputs as a workflow artifact, kept 14 days.
- **Prevention**: every number shown in a figure is also written to a table in `reports/data_audit`, which is compared. A figure without its table would not be checked.
