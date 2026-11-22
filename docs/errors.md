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
