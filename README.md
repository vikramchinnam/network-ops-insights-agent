# Network Ops Insights Agent

An AI assistant on Snowflake that answers questions about network health, support cases, and renewals for an enterprise networking customer base. It combines **Cortex Analyst** (metrics via a dbt-built semantic view) and **Cortex Search** (case notes, knowledge base, release notes) behind a **Cortex Agent**, with multi-tenant row-level security and GitHub-based CI/CD from Dev to Prod.

> **Disclaimer:** Synthetic data only. This project is modeled on an enterprise networking vendor's customer base and is not affiliated with or endorsed by any vendor.

## Architecture

```
Users (IT admins, partners, vendor support)
        │
Chat app (Python / FastAPI, Snowpark Container Services)
        │
Cortex Agent ──► Cortex Analyst ──► semantic view (dbt)
             └─► Cortex Search  ──► case notes, KB, release notes
        │
dbt models (Dev / Prod) with row access policies by customer and partner
        │
Raw synthetic data  ◄── Snowpark Python procedures (generator, health score, evals)
```

## Repo layout

| Folder | What lives there | Pipeline |
| --- | --- | --- |
| `infra/sql/` | Roles, warehouses, databases, cost guardrails, teardown | `infra.yml` |
| `dbt/` | Staging, marts, semantic view, search source tables | `dbt.yml` |
| `snowpark/` | Python stored procedures + `snowflake.yml` | `snowpark.yml` |
| `agent/` | Agent spec, Python API client, eval set | `agent.yml` |
| `spcs/` | Dockerfile, service spec, chat app | `spcs.yml` |
| `docs/` | Stage guides, adoption playbook | — |

## Roadmap

- [x] **Stage 1 — Foundations:** repo, Snowflake CLI, roles, warehouses, cost guardrails → [guide](docs/stages/01-foundations.md)
- [x] **Stage 2 — dbt basics:** synthetic data, staging and marts, Dev/Prod targets → [guide](docs/stages/02-dbt-basics.md)
- [x] **Stage 3 — Semantic view:** `dbt_semantic_view` package + Cortex Analyst → [guide](docs/stages/03-semantic-view.md)
- [x] **Stage 4 — Cortex Search:** case notes, KB articles, release notes → [guide](docs/stages/04-cortex-search.md)
- [ ] **Stage 5 — Cortex Agent:** agent spec, streaming Python client, evals → [5A guide](docs/stages/05a-cortex-agent.md); multi-tenant security → [5B guide](docs/stages/05b-tenant-security.md)
- [ ] **Stage 6 — Snowpark procedures + observability data:** generator, health score and eval procedures; dbt models for agent requests, AI cost and eval history
- [ ] **Stage 7 — Containers:** chat app on Snowpark Container Services with a live trace panel and an observability page (cost and quality)
- [ ] **Stage 8 — CI/CD:** GitHub Actions, OIDC, Dev → Prod approvals, review bot

## Quick start

```powershell
uv sync                                                    # Python env with Snowpark + dbt
uv run python -m noi_snowpark.generate_data --env dev      # load synthetic data
cd dbt; uv run dbt build; cd ..                             # build and test models
uv run python agent/deploy_agent.py --env dev              # deploy the Cortex Agent
uv run python agent/client.py "Is there a fix for roaming drops on 10.2.1?"
```

Full setup: [Stage 1 guide](docs/stages/01-foundations.md), then [Stage 2 guide](docs/stages/02-dbt-basics.md).
