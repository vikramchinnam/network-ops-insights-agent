# Stage 5A — Cortex Agent

**Goal:** a Cortex Agent, deployed from a version-controlled spec, that combines the semantic view and the search service to answer questions end to end; a Python client that streams its answers over the REST API; and an evaluation that scores it.

**Done when:** the agent answers in Snowsight and from `agent/client.py`, the agent eval scores at least 6/8 fully correct, and the work is merged through a PR.

**Time:** 1–2 days.

---

## How the agent works

```
question ──► Cortex Agent ──plan──► NetworkMetrics   (semantic view → SQL → numbers)
                          ├────────► KnowledgeBase    (search: KB articles + release notes)
                          └────────► CaseHistory      (search: support cases)
                                          │
                          ◄──── results ──┘
             writes one answer, citing numbers and KB IDs
```

The agent spec (`agent/network_ops_agent.yaml`) has four parts:

| Part | What it controls |
| --- | --- |
| `models.orchestration` | the LLM that plans and writes answers (one place to change it) |
| `orchestration.budget` | time and token limits per question: a cost guardrail |
| `instructions` | `system` (who it is), `orchestration` (when to use which tool), `response` (how to answer) |
| `tools` + `tool_resources` | the three tools and what each points at |

**Why two search tools:** Stage 4 showed support cases crowd out articles. `KnowledgeBase` filters to articles and release notes; `CaseHistory` filters to cases. Same service, different filters, chosen by the agent per question.

**A platform change to know about:** since April 2026, agents generate SQL from semantic views themselves. In responses, the metrics step appears as a tool of type `system_execute_sql`. The eval runner counts that as `NetworkMetrics`.

---

## 1. Branch, add files, install, test

```powershell
cd "C:\working\Agentic AI\network-ops-insights-agent"
git checkout main
git pull
git checkout -b stage-5a-cortex-agent
```

Copy the Stage 5A files in, then:

```powershell
uv sync
uv run pytest
```

**Check:** `12 passed`. These offline tests check the agent spec, the JWT signing, the stream parser and the eval scoring, without touching Snowflake. CI runs them on every PR in Stage 8.

## 2. Wake the search service

You suspended it before stepping away. Recreate it:

```powershell
cd dbt
uv run dbt build --select search_documents
cd ..
```

## 3. Deploy the agent

Look at the SQL first:

```powershell
uv run python agent/deploy_agent.py --env dev --dry-run
```

Read it: the YAML spec with `NOI_DEV` and `NOI_WH_DEV` filled in. Then deploy:

```powershell
uv run python agent/deploy_agent.py --env dev
```

**Check:** `Deployed NOI_DEV.AGENTS.NETWORK_OPS_AGENT`.

## 4. Talk to it in Snowsight

Open **AI & ML → Agents**, select `NETWORK_OPS_AGENT`, and ask:

- *Which access point firmware version has the most roaming failures?*
- *Is there a known fix for that?*
- *Why are hospitals seeing roaming problems, and what should they do?*

Expand the reasoning or trace panel to see which tools it called and the SQL it ran.

Or in a worksheet (role `NOI_DBT_DEV`):

```sql
SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'NOI_DEV.AGENTS.NETWORK_OPS_AGENT',
  $${"messages": [{"role": "user", "content": [{"type": "text",
     "text": "Is there a known fix for roaming failures on firmware 10.2.1?"}]}]}$$
)) AS response;
```

## 5. Talk to it from Python (REST API, streaming)

```powershell
uv run python agent/client.py "Why are hospitals seeing roaming problems, and what should they do?"
```

The answer prints word by word as it streams, with `[tool]` and `[status]` lines showing what the agent is doing. For a conversation:

```powershell
uv run python agent/client.py
```

Read `agent/client.py`: it signs a JWT with your private key, POSTs to `/api/v2/databases/NOI_DEV/schemas/AGENTS/agents/NETWORK_OPS_AGENT:run`, and parses Server-Sent Events. This is the same call your chat app's backend makes in Stage 7.

> The REST call runs as your user's **default role**. If you get a permissions error, check it with `DESC USER <your_login_name>;` (look at `DEFAULT_ROLE`) and set it with `ALTER USER <your_login_name> SET DEFAULT_ROLE = NOI_DBT_DEV;`.

## 6. Run the agent evaluation

```powershell
uv run python agent/evals/run_agent_eval.py
```

Eight questions, each checked two ways:

- **routing:** did the agent use the right tools? (`a08` checks it uses *none* for an off-topic question)
- **facts:** does the answer mention the required facts (e.g. `10.3.0`, `KB-1001`)?

Add `--show-answers` to read the answers, or `--only a03_why_and_what_to_do` to rerun one. Full details are saved to `agent/evals/results/` (JSON, gitignored).

Record the summary in `agent/evals/results/stage5a_agent_scorecard.md`: the three totals and any `FAIL` with what went wrong.

## 7. Improve what fails

| Symptom | Fix in `agent/network_ops_agent.yaml` |
| --- | --- |
| Uses KnowledgeBase for a number question | Sharpen the `orchestration` instruction or the NetworkMetrics `description` |
| Answers "why" questions with numbers only | Strengthen "for why questions, use NetworkMetrics then KnowledgeBase" |
| Doesn't cite KB IDs | Already in `response`; make it a must ("Always cite…") |
| Calls tools for off-topic questions | Strengthen the out-of-scope instruction |
| Times out | Raise `orchestration.budget.seconds` |
| Model not available | Change `models.orchestration` (e.g. `claude-sonnet-4-6`, `claude-haiku-4-5`) |

After each change: `uv run python agent/deploy_agent.py --env dev`, rerun the eval. Watch for regressions, as in Stage 4.

## 8. Commit through a PR

```powershell
git add .
git status        # no agent/evals/results/*.json
git commit -m "feat(agent): Cortex Agent spec, deploy script, streaming REST client, agent evals"
git push -u origin stage-5a-cortex-agent
gh pr create --fill
```

Put the eval totals in the PR description, merge, then `git checkout main` and `git pull`.

## Cost note

Each agent question bills tokens for planning, every tool it calls, and writing the answer. Eight eval questions cost little; avoid running the eval in a loop. When stepping away, run `infra/sql/99_teardown.sql` (the agent itself costs nothing while idle; the search service does).

---

## What you should be able to explain

- **Agent vs. tools:** the tools retrieve; the agent plans, chooses, combines and explains.
- **Why the spec is in Git:** the agent's behavior is code. It's reviewed in PRs, deployed by script, and identical in Dev and Prod.
- **Why two search tools over one service:** a measured finding (Stage 4) turned into a design decision.
- **Instructions as the main tuning lever:** routing and answer quality are mostly improved by clearer instructions and tool descriptions, measured by the eval.
- **REST vs. SQL access:** REST streams answers for UIs; `DATA_AGENT_RUN` returns one JSON response and runs as the SQL session's role, which is how evals and persona tests work.
- **Two levels of evaluation:** fast deterministic checks (routing, required facts) now; LLM-judged correctness and consistency in Stage 6.

## Troubleshooting

| Error | Likely cause | Fix |
| --- | --- | --- |
| `399504 ... missing an execution environment` | Analyst tool has no warehouse block | Keep `execution_environment: {type: warehouse, warehouse: ...}` under NetworkMetrics |
| Model not available / unsupported model | `models.orchestration` not offered in your region | Change the model name, redeploy |
| `HTTP 401` from client.py | JWT rejected | Check `SNOWFLAKE_ACCOUNT` (ORG-ACCOUNT form) and `SNOWFLAKE_USER` match your login; key registered in Stage 1 |
| `HTTP 404` from client.py | Agent not deployed, or wrong database | Run step 3; check `--env` |
| Tool not accessible / insufficient privileges | Default role can't use the agent or its tools | Set default role to `NOI_DBT_DEV` (step 5 note) |
| Search tools return nothing | Search service suspended | Step 2 |
