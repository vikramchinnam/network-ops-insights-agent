# Stage 3 — Semantic view and Cortex Analyst

**Goal:** a semantic view, built and tested by dbt, that lets Cortex Analyst answer business questions about the network in plain English.

**Done when:** `dbt build` passes (including the test that the semantic view matches the marts), Cortex Analyst answers at least 8 of the 10 evaluation questions correctly, and your scorecard is committed through a PR.

**Time:** 1–2 days.

---

## What a semantic view is

Your marts hold the data. A **semantic view** holds its *meaning*: which tables join to which, what "uptime" or "critical case" means, and what people call things ("tickets", "ARR", "APs"). Cortex Analyst reads the semantic view to turn a question into correct SQL.

```
"Which firmware has the most roaming problems?"
        │  Cortex Analyst reads the semantic view: synonyms, metrics, relationships
        ▼
SELECT firmware_version, AVG(roaming_failure_count) ... WHERE device_type = 'access_point' ...
        │
        ▼
Answer + the SQL it ran
```

Because the semantic view is a dbt model (`dbt/models/semantic/network_ops_analytics.sql`), it is version-controlled, reviewed in PRs, tested, and deployed Dev → Prod like everything else.

| Clause | In this project |
| --- | --- |
| `TABLES` | 6 logical tables over the marts, each with a primary key and synonyms |
| `RELATIONSHIPS` | health → devices → sites → customers; cases → sites; subscriptions → customers |
| `FACTS` | row-level numbers: uptime, disconnects, roaming failures, resolution hours, contract value |
| `DIMENSIONS` | what you group and filter by: industry, site type, model, firmware, severity, dates |
| `METRICS` | the answers: average uptime, open critical cases, MTTR, ARR renewing in 90 days |
| `AI_SQL_GENERATION` | plain-English rules for Analyst, such as "critical means P1 or P2" |

---

## 1. Branch and add the files

```powershell
cd "C:\working\Agentic AI\network-ops-insights-agent"
git checkout main
git pull
git checkout -b stage-3-semantic-view
```

Copy the Stage 3 files in, then `git status`. New: `dbt/packages.yml`, `dbt/models/semantic/`, `dbt/tests/assert_semantic_view_matches_mart.sql`, `agent/evals/`, this guide.

## 2. Install the dbt package

```powershell
cd dbt
uv run dbt deps
```

This downloads `Snowflake-Labs/dbt_semantic_view` into `dbt_packages/` (gitignored). It adds the `semantic_view` materialization used by the `semantic` folder in `dbt_project.yml`.

## 3. Build and test

```powershell
uv run dbt build
```

New in the output: the `network_ops_analytics` semantic view in `NOI_DEV.SEMANTIC`, and the test `assert_semantic_view_matches_mart`. That test asks the semantic view for roaming failures by firmware and checks the answer equals a direct query on the marts. It catches a wrong join or metric definition before Analyst ever uses it.

**Check:** `ERROR=0`.

## 4. Look at it in SQL

In a Snowsight worksheet (role `NOI_DBT_DEV`, warehouse `NOI_WH_DEV`):

```sql
SHOW SEMANTIC VIEWS IN SCHEMA NOI_DEV.SEMANTIC;
DESCRIBE SEMANTIC VIEW NOI_DEV.SEMANTIC.NETWORK_OPS_ANALYTICS;

-- Query it directly: you name metrics and dimensions, Snowflake writes the joins
SELECT * FROM SEMANTIC_VIEW(
    NOI_DEV.SEMANTIC.NETWORK_OPS_ANALYTICS
    DIMENSIONS customers.industry
    METRICS device_health.avg_uptime_pct, cases.open_critical_case_count
)
ORDER BY open_critical_case_count DESC;
```

Notice you never wrote a join: the relationships did it.

## 5. Ask Cortex Analyst

1. In Snowsight, open **AI & ML → Cortex Analyst** (menu names shift between releases; look for Cortex Analyst under AI & ML).
2. Set role `NOI_DBT_DEV` and warehouse `NOI_WH_DEV`.
3. Select the semantic view `NOI_DEV.SEMANTIC.NETWORK_OPS_ANALYTICS` and open its chat or playground.
4. Ask the 10 questions from `agent/evals/analyst_questions.yaml`, one at a time.
5. For each, run the question's `reference_sql` in a worksheet and compare the numbers. Analyst shows the SQL it generated: read it.
6. Record results in `agent/evals/results/stage3_analyst_scorecard.md`.

## 6. Improve what it gets wrong

This loop is the core skill of the stage, and the one interviewers ask about.

| Symptom | Likely fix in `network_ops_analytics.sql` |
| --- | --- |
| Picks the wrong column for a word | Add the word to that dimension's or metric's `WITH SYNONYMS` |
| Wrong business rule (e.g. counts P3 as critical) | Add the rule to `AI_SQL_GENERATION` or a metric `COMMENT` |
| Averages switches into Wi-Fi metrics | Already covered by `AI_SQL_GENERATION`; strengthen the wording if needed |
| Wrong date column for "last week" | Add synonyms to `metric_date` / `opened_date`, or clarify in instructions |
| Needs a number that doesn't exist | Add a new metric |

After each change: `uv run dbt build --select network_ops_analytics+`, then ask again. Record Run 2 in the scorecard.

> **Don't edit the semantic view in the Snowsight UI and stop there.** The next `dbt build` replaces it with what's in Git. The UI is a good place to experiment; Git is where the change has to land.

## 7. Optional: verified queries

Verified queries are question + SQL pairs that Analyst trusts and reuses. To learn the exact syntax without guessing: add one to a semantic view in the Snowsight UI, run `SELECT GET_DDL('SEMANTIC_VIEW', 'NOI_DEV.SEMANTIC.NETWORK_OPS_ANALYTICS');`, and copy the generated `AI_VERIFIED_QUERIES (...)` clause into the dbt model.

## 8. Commit through a PR

```powershell
cd ..
git add .
git status        # no dbt_packages/, no target/
git commit -m "feat(semantic): semantic view for Cortex Analyst, consistency test, eval set"
git push -u origin stage-3-semantic-view
gh pr create --fill
```

Paste your scorecard result into the PR description, merge, then `git checkout main` and `git pull`.

---

## What you should be able to explain

- **Semantic view vs. a regular view:** a regular view is one fixed query. A semantic view describes tables, joins, and metrics, so any combination of metrics and dimensions can be asked for, by SQL or by Analyst.
- **Why define metrics centrally:** "MTTR" or "ARR at risk" has one definition, used by dashboards, Analyst, and the agent alike.
- **Why the consistency test:** semantic views are code; the test proves a metric through the semantic view equals the same metric computed directly.
- **Why synonyms and comments matter:** they're the vocabulary Analyst uses to map language to columns. Most accuracy gains come from improving them, not from changing the model.
- **Relationship design:** cases join to sites (and through sites to customers) rather than directly to customers too, so there is exactly one join path and no ambiguity.

## Troubleshooting

| Error | Likely cause | Fix |
| --- | --- | --- |
| `materialization 'semantic_view' not found` | Package not installed | `uv run dbt deps` |
| `Insufficient privileges ... CREATE SEMANTIC VIEW` | Role can't create in schema | `NOI_DBT_DEV` owns `NOI_DEV`; confirm the profile role is `NOI_DBT_DEV` |
| Syntax error near a clause | Clause order matters | Keep `TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS, COMMENT, AI_SQL_GENERATION` |
| `assert_semantic_view_matches_mart` fails | Metric or relationship defined wrong | Compare the two values the test returns; fix the expression |
| Analyst says the semantic view isn't available | Role or AI access | Use role `NOI_DBT_DEV`; confirm the card was added (Stage 1) |
