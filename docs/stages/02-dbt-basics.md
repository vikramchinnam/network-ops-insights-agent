# Stage 2 — Synthetic data and dbt basics

**Goal:** realistic synthetic network data in `NOI_DEV.RAW`, transformed by dbt into tested staging views and mart tables, with Dev, CI and Prod targets defined.

**Done when:** `dbt build` finishes with every model and test passing, and the two exploration queries at the end return the planted patterns. The work is merged through a PR.

**Time:** 1–2 days.

---

## How the data flows

```
generate_data.py  ──►  NOI_DEV.RAW        7 tables, ~330k rows
                          │
                     dbt staging (views)  rename, cast, document  → NOI_DEV.STAGING
                          │
                     dbt marts (tables)   join, derive, test      → NOI_DEV.MARTS
```

| Mart | Grain | Used later for |
| --- | --- | --- |
| `dim_customer` | one row per customer | tenant keys (`customer_id`, `partner_id`) for row-level security |
| `dim_site` | one row per site | filtering by site type (hospital, school, stadium) |
| `dim_device` | one row per device | firmware and end-of-sale questions |
| `fct_device_health_daily` | device × day | uptime, disconnects, roaming and auth failures |
| `fct_support_cases` | one row per case | case metrics (Analyst) and case text (Search) |
| `fct_subscriptions` | one row per subscription | renewal risk |

**Planted signals** the agent should find in later stages:
- Access points on firmware **10.2.1** have about 4× more roaming failures, and most "Wi-Fi roaming" cases.
- Model **AX-200** reaches end of sale on 2026-12-31.
- Several customers renew within 90 days **and** have open P1/P2 cases.

---

## 1. Start a branch and add the files

```powershell
cd "C:\working\Agentic AI\network-ops-insights-agent"
git checkout main
git pull
git checkout -b stage-2-dbt-basics
```

Copy the Stage 2 files into the repo, then check what changed:

```powershell
git status
```

## 2. Install the Python environment

```powershell
uv sync
```

This reads `pyproject.toml`, downloads a matching Python if needed, creates `.venv`, and installs Snowpark, dbt and the generator's libraries. `uv run <command>` then runs anything inside that environment.

## 3. Set your connection environment variables (once)

dbt and the generator both read these, so credentials stay out of the repo. Replace the placeholders:

```powershell
[Environment]::SetEnvironmentVariable("SNOWFLAKE_ACCOUNT", "<ORGNAME-ACCOUNTNAME>", "User")
[Environment]::SetEnvironmentVariable("SNOWFLAKE_USER", "<your_login_name>", "User")
[Environment]::SetEnvironmentVariable("SNOWFLAKE_PRIVATE_KEY_PATH", "$($HOME -replace '\\','/')/.snowflake/keys/noi_rsa_key.p8", "User")
```

Fully exit VS Code (File → Exit) and reopen it, then check:

```powershell
$env:SNOWFLAKE_ACCOUNT
```

## 4. Look at the data before loading it

```powershell
uv run python -m noi_snowpark.generate_data --dry-run
```

This writes CSVs to `data/` (gitignored) without touching Snowflake. Open `data/support_cases.csv` and `data/devices.csv` in VS Code and get a feel for the data.

## 5. Load it into Snowflake

```powershell
uv run python -m noi_snowpark.generate_data --env dev
```

Expected output: seven `loaded ...` lines, the largest being `DEVICE_HEALTH_DAILY` at roughly 320,000 rows. Rerunning replaces the tables.

## 6. Run dbt

```powershell
cd dbt
uv run dbt debug      # checks the profile and connection: look for "All checks passed!"
uv run dbt build      # runs models and tests in dependency order
cd ..
```

`dbt build` creates 7 staging views and 6 mart tables, and runs about 35 tests. Read the summary line at the end: `PASS=… WARN=0 ERROR=0`.

## 7. Explore the results

In a Snowsight worksheet, using role `NOI_DBT_DEV` and warehouse `NOI_WH_DEV`:

```sql
-- Roaming failures by access point firmware: 10.2.1 should stand out
select firmware_version,
       round(avg(roaming_failure_count), 2) as avg_daily_roaming_failures
from NOI_DEV.MARTS.FCT_DEVICE_HEALTH_DAILY
where device_type = 'access_point'
group by 1
order by 2 desc;

-- Customers renewing within 90 days that have open critical cases
select c.customer_name, c.industry, s.product, s.days_to_renewal, s.annual_value_usd,
       count(distinct k.case_id) as open_critical_cases
from NOI_DEV.MARTS.FCT_SUBSCRIPTIONS s
join NOI_DEV.MARTS.DIM_CUSTOMER c on s.customer_id = c.customer_id
join NOI_DEV.MARTS.FCT_SUPPORT_CASES k
  on k.customer_id = s.customer_id and k.is_open and k.is_critical
where s.is_renewing_within_90_days
group by 1, 2, 3, 4, 5
order by s.days_to_renewal;
```

These are exactly the kinds of questions the agent will answer in natural language from Stage 3 onward.

## 8. Commit through a PR

```powershell
git add .
git status        # confirm: no data/ folder, no .p8, no config.toml
git commit -m "feat(dbt): synthetic data generator, staging and mart models, tests"
git push -u origin stage-2-dbt-basics
gh pr create --fill
```

Merge it on GitHub (Squash and merge), then `git checkout main` and `git pull`.

---

## What you should be able to explain

- **Staging vs. marts:** staging is a thin, one-to-one cleanup of each source (views, cheap). Marts join and derive business concepts (tables, fast to query). Analysts and the agent only read marts.
- **Grain:** every model has one documented grain, and a test enforces it (`unique` keys, the device × day singular test).
- **Why `profiles.yml` is committed:** it holds no secrets, only `env_var()` lookups, so the same file works on your laptop and in CI.
- **Why three targets:** `dev` for you, `ci` for isolated per-PR schemas (Stage 8), `prod` deployed only by CI. The `generate_schema_name` macro decides where each model lands.
- **Why the generator is seeded:** same seed and `--as-of` date give identical data, which makes evaluations repeatable.
- **A known simplification:** `fct_device_health_daily` uses each device's *current* firmware. A real system would track firmware history (a slowly changing dimension).

## Troubleshooting

| Error | Likely cause | Fix |
| --- | --- | --- |
| `KeyError: 'SNOWFLAKE_ACCOUNT'` | Env vars not set, or VS Code not restarted | Redo step 3, fully exit and reopen VS Code |
| `Env var required but not provided` (dbt) | Same as above | Same as above |
| `Insufficient privileges ... schema RAW` | Generator ran as the wrong role | It uses `NOI_DBT_DEV`; rerun `infra/sql/00_roles.sql` and `02_databases.sql` |
| `Object 'NOI_DEV.RAW.DEVICES' does not exist` in dbt | Data not loaded yet | Run step 5 first |
| `No module named noi_snowpark` | Environment not synced | Run `uv sync` from the repo root |
