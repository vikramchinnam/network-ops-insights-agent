# Stage 4 — Cortex Search

**Goal:** a Cortex Search service, built by dbt, that finds the right support case, knowledge base article or release note for a question asked in everyday words.

**Done when:** `dbt build` creates the `SUPPORT_DOCS` search service, the search evaluation scores at least 8/10 (hit@5) with `--docs-only`, and the work is merged through a PR.

**Time:** half a day.

---

## Why search, and why by meaning

Cortex Analyst answers questions about **numbers**. Many support questions are about **text**: "is there a known fix", "has anyone seen this". Cortex Search indexes text and matches by meaning (vector embeddings) and keywords together, so *"clients drop when walking between APs"* finds an article titled *"client roaming failures on firmware 10.2.1"* even though the words differ.

```
generate_data.py ──► RAW.KB_ARTICLES, RAW.RELEASE_NOTES (new)    RAW.SUPPORT_CASES
                          │                                          │
                     stg_kb_articles, stg_release_notes          fct_support_cases
                          └───────────────┬──────────────────────────┘
                                 search_documents (table, one row per document)
                                          │  post-hook
                                 Cortex Search service SUPPORT_DOCS
```

| Column | Role in search |
| --- | --- |
| `content` | the text that gets indexed (title + body) |
| `doc_type` | filter: `kb_article`, `release_note`, `support_case` |
| `firmware_version`, `product_models`, `category`, `industry` | filters for narrowing results |
| `customer_id`, `partner_id` | tenant keys; NULL for public documents. Used for tenant filtering in Stage 5 |

**The planted story:** firmware 10.2.1 has a roaming bug (Stage 2 data). Now the documents explain it: KB-1001 describes the issue and workaround, and the 10.3.0 release notes say it is fixed. In Stage 5 the agent connects the numbers (Analyst) to the explanation (Search).

---

## 1. Branch and add the files

```powershell
cd "C:\working\Agentic AI\network-ops-insights-agent"
git checkout main
git pull
git checkout -b stage-4-cortex-search
```

Copy the Stage 4 files in, then `git status`. New: `knowledge_base.py`, `models/search/`, the search macro, two staging models, `agent/evals/search_queries.yaml`, `agent/evals/run_search_eval.py`, this guide.

```powershell
uv sync
```

(`pyyaml` was added for the eval runner.)

## 2. Regenerate the data

```powershell
uv run python -m noi_snowpark.generate_data --env dev
```

**Check:** two new lines, `KB_ARTICLES` (15 rows) and `RELEASE_NOTES` (5 rows). Existing tables are replaced with identical data, since the seed hasn't changed.

## 3. Build

```powershell
cd dbt
uv run dbt build
```

New in the output: `stg_kb_articles`, `stg_release_notes`, and `search_documents`. After `search_documents` is built, its post-hook runs `create or replace cortex search service NOI_DEV.SEARCH.SUPPORT_DOCS`. Building the index takes a minute or two.

**Check:** `ERROR=0`. Then in Snowsight (role `NOI_DBT_DEV`):

```sql
SHOW CORTEX SEARCH SERVICES IN SCHEMA NOI_DEV.SEARCH;
```

The service is listed. Its indexing state should become active shortly.

## 4. Try it in SQL

```sql
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'NOI_DEV.SEARCH.SUPPORT_DOCS',
  '{"query": "clients drop when walking between access points",
    "columns": ["doc_id", "doc_type", "title"],
    "limit": 5}'
)):results AS results;
```

Then with a filter, to return only articles and release notes:

```sql
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'NOI_DEV.SEARCH.SUPPORT_DOCS',
  '{"query": "clients drop when walking between access points",
    "columns": ["doc_id", "doc_type", "title"],
    "filter": {"@not": {"@eq": {"doc_type": "support_case"}}},
    "limit": 5}'
)):results AS results;
```

Compare the two. Without the filter, many of the 650 support cases describe the same symptom and compete with the KB article.

You can also open **AI & ML → Cortex Search** in Snowsight, select `SUPPORT_DOCS`, and use its playground.

## 5. Run the search evaluation

From the repo root:

```powershell
cd ..
uv run python agent/evals/run_search_eval.py
uv run python agent/evals/run_search_eval.py --docs-only
```

Each run prints one line per query (hit, rank, top result) and two scores:

- **hit@5:** how many queries had a correct document in the top 5.
- **MRR:** how high the correct document ranked, on average (1.0 = always first).

Record both runs in a new file, `agent/evals/results/stage4_search_scorecard.md`. Expect `--docs-only` to score higher. That finding matters for Stage 5: the agent should search articles first for "is there a fix" questions, and cases for "has this happened before" questions.

## 6. Improve what misses

| Symptom | Fix |
| --- | --- |
| Right article ranks low because cases crowd it out | Use a `doc_type` filter for that kind of question (Stage 5 agent instructions) |
| Article never appears | Its wording is too far from how people ask: add a "Symptom:" sentence in plain words in `knowledge_base.py` |
| Wrong article ranks first | Titles carry weight; make titles specific |
| Need better semantic matching | Try `EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'` in the macro (check regional availability) |

After changing content: regenerate (step 2), `dbt build --select search_documents`, rerun the eval.

## 7. Commit through a PR

```powershell
git add .
git status
git commit -m "feat(search): knowledge base, search documents model, Cortex Search service, search evals"
git push -u origin stage-4-cortex-search
gh pr create --fill
```

Add your hit@5 and MRR to the PR description, merge, then `git checkout main` and `git pull`.

## Cost note

A search service bills for serving and indexing while it exists, not only when queried. When you step away for more than a day, run:

```powershell
snow sql -f infra/sql/99_teardown.sql -c noi
```

It now suspends the service; the next `dbt build` recreates it.

---

## What you should be able to explain

- **Search vs. Analyst:** Analyst writes SQL over structured data; Search retrieves passages of text. The agent (Stage 5) chooses between them.
- **Hybrid search:** Cortex Search combines vector similarity (meaning) and keyword matching, so both "roaming bug" and the exact error text work.
- **Why one documents table:** one service, one set of filters, one place to add new document types.
- **Attributes as filters:** narrowing by `doc_type` or `firmware_version` at query time improves precision, and the tenant columns enable per-customer filtering later.
- **Why measure hit@5 and MRR:** "the search seems good" isn't evidence; a fixed query set with expected documents is.
- **Why the service is rebuilt in a post-hook:** dbt replaces the table on each build, so the service is recreated to point at it; the document set is small, so this is cheap.

## Troubleshooting

| Error | Likely cause | Fix |
| --- | --- | --- |
| `Object 'RAW.KB_ARTICLES' does not exist` | Data not regenerated | Run step 2 |
| `Insufficient privileges to operate on schema 'SEARCH'` | Wrong role | Profile role must be `NOI_DBT_DEV`, which owns `NOI_DEV` |
| `Cortex Search service ... does not exist` in the eval | Post-hook failed or still building | Check the `dbt build` log for the post-hook; wait a minute and retry |
| Eval says `No module named yaml` | Environment out of date | `uv sync` |
| Model or embedding errors on create | Embedding model availability | Keep the default embedding model (the macro doesn't set one) |
