# Stage 6 — Snowpark procedures and observability data

**Goal:** move scheduled work from your laptop into Snowflake as Snowpark Python stored procedures, deployed with the Snowflake CLI and scheduled by Tasks; and build the observability data (cost, requests, eval history and traces) that the Stage 7 UI will show.

**Done when:** the three procedures run in Snowflake, health scores are filtered per partner, eval runs are stored with their full traces, the observability views return data, and the work is merged through a PR.

**Time:** 1 day.

---

## What runs where

```
your laptop                                    Snowflake: NOI_DEV.OPS
cd snowpark
snow snowpark build ──► zip of src/noi_snowpark
snow snowpark deploy ─────────────────────►    GENERATE_DATA(days, seed)
                                               COMPUTE_CUSTOMER_HEALTH()   → OPS.CUSTOMER_HEALTH_SCORES (+ history)
                                               RUN_AGENT_EVAL(agent_fqn)   → OPS.AGENT_EVAL_RUNS (with full responses)
                                                       ▲
                                    TASK_CUSTOMER_HEALTH  daily 6:00
                                    TASK_AGENT_EVAL       Mondays 7:00   (created suspended)

dbt  OBSERVABILITY schema (views):  fct_agent_requests · fct_ai_cost_daily · fct_eval_runs
                                    over SNOWFLAKE.ACCOUNT_USAGE + OPS.AGENT_EVAL_RUNS
```

| Procedure | Snowpark skill it shows |
| --- | --- |
| `GENERATE_DATA` | Reusing the same Python package locally and in Snowflake; `write_pandas` into a named schema |
| `COMPUTE_CUSTOMER_HEALTH` | **DataFrame API**: filters, joins, aggregations and scoring written in Python, run as SQL inside Snowflake; unit-tested with Snowpark **local testing** |
| `RUN_AGENT_EVAL` | Calling the Cortex Agent from a procedure; storing results and full responses as VARIANT for tracing |

**Health score rules** (in `procedures.py`): start at 100; subtract 10 per point of 7-day uptime below 100 (max 40), 5 per daily roaming failure above 2 (max 25), 10 per open critical case (max 30), and 10 if renewing within 90 days with open critical cases. Tiers: ≥ 80 Healthy, ≥ 60 Watch, otherwise At risk.

**Two design choices:**
- **One implementation, two runtimes.** `noi_snowpark/agent_eval.py` holds the eval logic, used by both `run_agent_eval.py` on your laptop and the `RUN_AGENT_EVAL` procedure. The question set moved into the package so it ships with the procedure.
- **Tables created once, refilled by the procedure.** `deploy_ops.py setup` creates the health tables; the procedure truncates and refills them. Grants and the tenant policy persist, unlike a table that's dropped and recreated each run.

---

## 1. Branch, move one file, add the files

```powershell
cd "C:\working\Agentic AI\network-ops-insights-agent"
git checkout main
git pull
git checkout -b stage-6-snowpark-procedures
```

The agent question set moves into the Python package. Move it with Git first, so its history follows it:

```powershell
git mv agent/evals/agent_questions.yaml snowpark/src/noi_snowpark/agent_questions.yaml
```

Then copy the Stage 6 files in and check:

```powershell
git status
git diff
```

New: `snowpark/snowflake.yml`, `snowpark/requirements.txt`, `snowpark/deploy_ops.py`, `snowpark/src/noi_snowpark/procedures.py`, `snowpark/src/noi_snowpark/agent_eval.py`, `infra/sql/06_ops_privileges.sql`, `dbt/models/observability/`, three new test files, this guide.

## 2. Install and test

```powershell
uv sync
uv run pytest
```

**Check:** `26 passed`. Three of them run the health score logic in **Snowpark local testing** mode: DataFrame code executed without any Snowflake connection.

## 3. Grant the new privileges

```powershell
snow sql -f infra/sql/06_ops_privileges.sql -c noi
```

Lets the build roles run Tasks and read Snowflake's usage views.

## 4. Create the OPS schema and tables

```powershell
uv run python snowpark/deploy_ops.py setup --env dev
```

**Check:** `setup: done for NOI_DEV.OPS`.

## 5. Build dbt (wakes search services, adds observability views)

```powershell
cd dbt
uv run dbt build
cd ..
```

**Check:** `ERROR=0`, with three new views in `NOI_DEV.OBSERVABILITY`.

## 6. Build and deploy the procedures with the Snowflake CLI

```powershell
cd snowpark
snow snowpark build -c noi
snow snowpark deploy --replace -c noi --database NOI_DEV --schema OPS --role NOI_DBT_DEV --warehouse NOI_WH_DEV
cd ..
```

- `build` reads `snowflake.yml` and `requirements.txt`, checks the packages against Snowflake's Anaconda channel, and zips `src/noi_snowpark`.
- `deploy` uploads the zip to the `SNOWPARK_ARTIFACTS` stage and creates the three procedures. `--replace` updates them if they exist.

**Check:** a table listing `GENERATE_DATA`, `COMPUTE_CUSTOMER_HEALTH` and `RUN_AGENT_EVAL` as created.

Then grant read access to the persona roles:

```powershell
uv run python snowpark/deploy_ops.py grants --env dev
```

## 7. Run the procedures

In a Snowsight worksheet (role `NOI_DBT_DEV`, warehouse `NOI_WH_DEV`):

```sql
CALL NOI_DEV.OPS.COMPUTE_CUSTOMER_HEALTH();
-- {"table": "...CUSTOMER_HEALTH_SCORES", "customers": 40, "tiers": {...}}

SELECT customer_name, industry, health_score, risk_tier, open_critical_cases, renewing_90d
FROM NOI_DEV.OPS.CUSTOMER_HEALTH_SCORES
ORDER BY health_score
LIMIT 10;

CALL NOI_DEV.OPS.RUN_AGENT_EVAL('NOI_DEV.AGENTS.NETWORK_OPS_AGENT');
-- {"run_id": "...", "fully_correct": 8, "questions": 8}   (takes a few minutes)
```

Optionally, regenerate the data from inside Snowflake (same seed, so the same data):

```sql
CALL NOI_DEV.OPS.GENERATE_DATA(60, 42);
```

## 8. Look at what you now have

**Health scores, filtered per partner:**

```sql
USE ROLE NOI_PARTNER_PTR_001;
USE SECONDARY ROLES NONE;
SELECT partner_id, COUNT(*), AVG(health_score) FROM NOI_DEV.OPS.CUSTOMER_HEALTH_SCORES GROUP BY 1;
-- only PTR-001
USE ROLE NOI_DBT_DEV;
USE SECONDARY ROLES ALL;
```

**Traces: what the agent did for each eval question:**

```sql
SELECT r.question_id,
       r.routing_ok,
       t.value:tool_use:name::varchar  AS tool,
       t.value:tool_use:input          AS tool_input
FROM NOI_DEV.OPS.AGENT_EVAL_RUNS r,
     LATERAL FLATTEN(input => r.response:content) t
WHERE t.value:type = 'tool_use'
  AND r.run_id = (SELECT MAX_BY(run_id, run_at) FROM NOI_DEV.OPS.AGENT_EVAL_RUNS)
ORDER BY r.question_id;
```

**Observability views** (usage views lag by a few hours, so recent runs may not appear yet):

```sql
SELECT * FROM NOI_DEV.OBSERVABILITY.FCT_EVAL_RUNS ORDER BY run_at DESC;
SELECT * FROM NOI_DEV.OBSERVABILITY.FCT_AI_COST_DAILY ORDER BY usage_date DESC, credits DESC;
SELECT DATE(start_time) AS day, COUNT(*) AS requests,
       ROUND(SUM(credits) / COUNT(*), 5) AS credits_per_request
FROM NOI_DEV.OBSERVABILITY.FCT_AGENT_REQUESTS GROUP BY 1 ORDER BY 1 DESC;
```

## 9. Schedule them

```powershell
uv run python snowpark/deploy_ops.py tasks --env dev
```

Tasks are created **suspended**. Run one once by hand to see it work:

```sql
EXECUTE TASK NOI_DEV.OPS.TASK_CUSTOMER_HEALTH;

SELECT name, state, scheduled_time, completed_time, error_message
FROM TABLE(NOI_DEV.INFORMATION_SCHEMA.TASK_HISTORY())
ORDER BY scheduled_time DESC LIMIT 5;
```

Leave them suspended during the trial unless you want the schedule to run (`--resume`). `99_teardown.sql` now suspends them too.

## 10. Commit through a PR

```powershell
git add .
git status
git commit -m "feat(snowpark): stored procedures, tasks, observability models"
git push -u origin stage-6-snowpark-procedures
gh pr create --fill
```

Merge, then `git checkout main` and `git pull`.

---

## What you should be able to explain

- **Why stored procedures:** scheduled work runs where the data lives, with Snowflake's security and no laptop or extra server.
- **DataFrame API vs. SQL strings:** the health score is Python that Snowflake compiles to SQL and runs on the warehouse; data never leaves Snowflake, and the logic is unit-testable with local testing.
- **Owner's rights:** procedures run as their owner (`NOI_DBT_DEV`), so callers don't need direct access to every table. The output table still carries the tenant policy, so partners see only their rows.
- **Snowflake CLI project definition:** `snowflake.yml` declares the procedures; `requirements.txt` declares packages; the same files deploy to Dev or Prod by changing command-line flags.
- **Observability from two sources:** Snowflake's usage views (billed credits, lagging hours) and your own eval table (immediate, with full traces).
- **Tasks created suspended:** schedules are opt-in, so nothing spends credits unexpectedly.

## Troubleshooting

| Error | Likely cause | Fix |
| --- | --- | --- |
| `Object 'OPS.AGENT_EVAL_RUNS' does not exist` in dbt | Setup skipped | Step 4, then rebuild |
| `Insufficient privileges ... ACCOUNT_USAGE` in observability views | Privileges not granted | Step 3 |
| `snow snowpark build` reports a package unavailable | Not in Snowflake's Anaconda channel | The CLI downloads it into the zip; if that fails, tell me which package |
| `Procedure ... already exists` | Missing `--replace` | Add `--replace` |
| `COMPUTE_CUSTOMER_HEALTH`: row access policy does not exist | dbt seed hooks haven't run | Step 5 |
| `RUN_AGENT_EVAL` records errors | Agent or search services not available | Redeploy agents; Step 5 wakes the services |
| `EXECUTE TASK` not authorized | Task privilege missing | Step 3 |
