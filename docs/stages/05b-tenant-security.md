# Stage 5B — Multi-tenant security

**Goal:** each partner sees only its own customers' data through every path (direct SQL, the semantic view, search and the agent), enforced by the data platform rather than by prompts, and proven by tests that try to break it.

**Done when:** `run_tenant_eval.py` reports `NO LEAKS` for every persona, the internal agent eval still scores 8/8, and the work is merged through a PR.

**Time:** 1 day.

---

## The principle

> Security lives in the data platform. The agent inherits it. Tests try to break it.

An instruction like "only show partner A's data" can be talked around. A row access policy can't: the database filters rows before the agent ever sees them.

## The design

```
                         who is asking? (CURRENT_ROLE)
                                   │
   ┌───────────────────────────────┼─────────────────────────────────┐
   │ Numbers                       │ Text                            │
   │ TENANT_POLICY on every mart   │ SUPPORT_DOCS  internal only     │
   │ filters rows by partner_id    │ PUBLIC_DOCS   KB + release notes│
   └───────────────┬───────────────┴───────────────┬─────────────────┘
                   │                               │
     NETWORK_OPS_AGENT (internal)       NETWORK_OPS_PARTNER_AGENT
     Metrics + KB + CaseHistory         Metrics + KB(PUBLIC_DOCS)
     usage: NOI_SUPPORT                 usage: partner roles
```

| Piece | Where | What it does |
| --- | --- | --- |
| Persona roles | `infra/sql/05_tenant_roles.sql` | `NOI_SUPPORT`, `NOI_PARTNER_PTR_001`, `NOI_PARTNER_PTR_002` |
| Role → partner mapping | `dbt/seeds/tenant_access.csv` | Version-controlled: access changes go through a PR |
| Row access policy | `dbt/macros/tenant_security.sql` | `TENANT_POLICY`: exempt roles see all; others see rows mapped to `CURRENT_ROLE()` |
| Policy on every mart | `dbt_project.yml` post-hooks | Reattached each time dbt rebuilds a mart |
| Grants | dbt `on-run-end` | Personas get SELECT on marts and the semantic view; partners get only `PUBLIC_DOCS` |
| Public search service | `dbt/models/search/public_documents.sql` | KB and release notes only; partners can't reach case text |
| Partner agent | `agent/network_ops_partner_agent.yaml` | No CaseHistory; KnowledgeBase on `PUBLIC_DOCS` |
| Leakage tests | `agent/evals/run_tenant_eval.py` | Tables, semantic view, search and agent probes per persona; exits 1 on any failure |

**Two decisions worth explaining:**

- **`CURRENT_ROLE()`, not `IS_ROLE_IN_SESSION()`.** With secondary roles enabled, a partner session can also carry your admin roles; `IS_ROLE_IN_SESSION('NOI_ADMIN')` would be true and the partner would see everything. `CURRENT_ROLE()` checks only the primary role.
- **A separate `PUBLIC_DOCS` service instead of a filter.** A filter in an agent spec only constrains that agent. A partner with USAGE on `SUPPORT_DOCS` could call it directly and read every case. Grants close that path; filters don't.

---

## 1. Branch and add the files

```powershell
cd "C:\working\Agentic AI\network-ops-insights-agent"
git checkout main
git pull
git checkout -b stage-5b-tenant-security
```

Copy the Stage 5B files in, then:

```powershell
git status
git diff
```

**Check:** new files include `infra/sql/05_tenant_roles.sql`, `dbt/seeds/`, `dbt/macros/tenant_security.sql`, `dbt/models/search/public_documents.sql`, `agent/network_ops_partner_agent.yaml`, `agent/evals/run_tenant_eval.py`, `tests/test_tenant_eval.py`, this guide. Your Stage 5A scorecard is not in the zip, so it stays as you wrote it.

## 2. Install and test

```powershell
uv sync
uv run pytest
```

**Check:** `19 passed`.

## 3. Create the persona roles

```powershell
snow sql -f infra/sql/05_tenant_roles.sql -c noi
```

**Check:** no errors. The three roles exist and are granted to you so you can test as each.

## 4. Build: policy, public search service and grants

```powershell
cd dbt
uv run dbt build
cd ..
```

What's new in the output:
- `seed tenant_access` loads into `NOI_DEV.SECURITY`, and its post-hooks create `TENANT_POLICY`
- every mart runs two post-hooks: drop old policies, attach `TENANT_POLICY` on `partner_id`
- `public_documents` builds, and its post-hook creates the `PUBLIC_DOCS` search service
- at the end: `Granted consumer access to NOI_SUPPORT, NOI_PARTNER_PTR_001, NOI_PARTNER_PTR_002`

**Check:** `ERROR=0`. Then in Snowsight (role `NOI_DBT_DEV`):

```sql
SHOW ROW ACCESS POLICIES IN SCHEMA NOI_DEV.SECURITY;

SELECT ref_entity_name, ref_column_name, policy_name
FROM TABLE(NOI_DEV.INFORMATION_SCHEMA.POLICY_REFERENCES(
  POLICY_NAME => 'NOI_DEV.SECURITY.TENANT_POLICY'));
```

The second query lists all six marts.

## 5. See it with your own eyes

In a Snowsight worksheet:

```sql
USE ROLE NOI_PARTNER_PTR_001;
USE SECONDARY ROLES NONE;   -- only this role's privileges, as a real partner user would have
USE WAREHOUSE NOI_WH_DEV;

SELECT partner_id, COUNT(*) FROM NOI_DEV.MARTS.DIM_CUSTOMER GROUP BY 1;
-- one row: PTR-001

SELECT * FROM SEMANTIC_VIEW(NOI_DEV.SEMANTIC.NETWORK_OPS_ANALYTICS
  DIMENSIONS customers.partner_name METRICS customers.customer_count);
-- one partner only

SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('NOI_DEV.SEARCH.SUPPORT_DOCS',
  '{"query": "roaming", "columns": ["doc_id"], "limit": 3}');
-- error: insufficient privileges

USE ROLE NOI_SUPPORT;
SELECT partner_id, COUNT(*) FROM NOI_DEV.MARTS.DIM_CUSTOMER GROUP BY 1;
-- all partners
```

Same table, same query, different answers by role. Run `USE SECONDARY ROLES ALL;` afterwards to restore your normal session.

## 6. Deploy both agents

```powershell
uv run python agent/deploy_agent.py --env dev --dry-run
uv run python agent/deploy_agent.py --env dev
```

**Check:** two lines: `Deployed NOI_DEV.AGENTS.NETWORK_OPS_AGENT (usage granted to NOI_SUPPORT)` and `Deployed NOI_DEV.AGENTS.NETWORK_OPS_PARTNER_AGENT (usage granted to NOI_PARTNER_PTR_001, NOI_PARTNER_PTR_002)`.

## 7. Run the leakage tests

Data layer first (fast, no AI cost):

```powershell
uv run python agent/evals/run_tenant_eval.py --skip-agent
```

Then everything, including agent probes (12 agent runs):

```powershell
uv run python agent/evals/run_tenant_eval.py
```

For each persona you'll see checks like:

```
NOI_PARTNER_PTR_001  (scope: PTR-001, agent: partner)
  pass  tables:DIM_CUSTOMER        sees ['PTR-001']
  pass  semantic_view              sees ['Smith Networks']
  pass  search:PUBLIC_DOCS         allowed
  pass  search:SUPPORT_DOCS        denied (...)
  pass  agent:probe4               no foreign names
```

Probe 4 is a prompt-injection attempt ("ignore your instructions, I'm an administrator…"). It fails to leak because the data was never there to leak, not because the model resisted.

**Check:** the last line says `NO LEAKS.` and the script exits with code 0.

## 8. Confirm nothing regressed

```powershell
uv run python agent/evals/run_agent_eval.py
```

**Check:** still 8/8. (It runs as `NOI_DBT_DEV`, an exempt role, so it sees all data.)

## 9. Try the partner experience

In Snowsight, switch your role to `NOI_PARTNER_PTR_001`, open **AI & ML → Agents**: only the partner agent is listed. Ask *"Which of my customers renew in the next 90 days?"* and *"List all partners and their customers."*

## 10. Scorecard and PR

Fill in `agent/evals/results/stage5b_tenant_scorecard.md`, then:

```powershell
git add .
git status
git commit -m "feat(security): row access policies, partner agent, public search service, leakage tests"
git push -u origin stage-5b-tenant-security
gh pr create --fill
```

In the PR description: "Tenant eval: N/N checks, no leaks." Merge, then `git checkout main`, `git pull`.

---

## What you should be able to explain

- **Where security lives:** row access policies and grants. The agent runs as the caller's role and inherits the filter; no prompt can widen it.
- **Why the mapping is a dbt seed:** access is reviewed like code, with history of who changed what and when.
- **Why `CURRENT_ROLE()`:** secondary roles would otherwise let a partner session inherit an exempt role.
- **Why a second search service:** filters constrain an agent; grants constrain a role. Only the second closes direct access.
- **How you know it works:** a test suite that attacks each path as each persona, with a hard exit code CI can gate on, including a prompt-injection probe.
- **A known trade-off:** dbt recreates each mart and then reattaches the policy in a post-hook, so there's a brief window during a build where a newly created table has no policy. Only build roles can see the schema mid-build, but a production setup could close it with `copy_grants`-style patterns or by applying policies through tags.

## Troubleshooting

| Error | Likely cause | Fix |
| --- | --- | --- |
| `Role 'NOI_SUPPORT' does not exist` in dbt on-run-end | Step 3 skipped | Run `05_tenant_roles.sql`, rebuild |
| `Row access policy ... does not exist` on a mart | Seed hooks didn't run | `uv run dbt build --select tenant_access+` |
| Partner sees all partners in Snowsight | Secondary roles active | `USE SECONDARY ROLES NONE;` |
| Partner sees nothing ("grants?") | on-run-end grants didn't run | Rebuild; look for "Granted consumer access" in the log |
| `search:PUBLIC_DOCS` fails | Service not built yet | `uv run dbt build --select public_documents` |
| Agent probe errors for partners | Partner agent not deployed or no USAGE | Step 6 |
