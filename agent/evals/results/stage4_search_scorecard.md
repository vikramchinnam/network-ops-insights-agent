# Stage 4 — Cortex Search scorecard

Service: `NOI_DEV.SEARCH.SUPPORT_DOCS` · Date run: 2026-10-31 · Eval set: `agent/evals/search_queries.yaml` (10 queries)

## Metrics

- **hit@5:** share of queries where an expected document appears in the top 5 results
- **MRR (mean reciprocal rank):** average of 1/rank of the first expected document (1.0 = always ranked first)

## Baseline: all documents vs. articles and release notes only

| Run | hit@5 | MRR | Misses |
| --- | --- | --- | --- |
| All documents (incl. 650 support cases) | 9/10 (90%) | 0.85 | s08: support cases about slow Wi-Fi outranked KB-1008; s09 ranked 2nd |
| Docs only (`--docs-only`) | 10/10 (100%) | 0.95 | s09 ranked 2nd |

## Tuning attempts (docs only)

| Version | hit@5 | MRR | Change | Result |
| --- | --- | --- | --- | --- |
| v1 | 10/10 | 0.95 | Baseline | s09 at rank 2 (KB-1005 above KB-1010) |
| v2 | 10/10 | 0.95 | KB-1010 retitled "RMA: replacing a failed or dead device" | s09 moved to rank 1, but another query dropped to rank 2 (regression) |
| v3 | 10/10 | 0.95 | KB-1005 retitled "AX-200 end of sale: recommended replacement model is the AX-400" | s06 at rank 1, s09 back to rank 2 |
| v4 | 10/10 | 0.95 | KB-1005 retitled "AX-200 end of sale: upgrade path to the AX-400" (removed shared word "replacement") | No change: s09 still rank 2 |

**Final:** hit@5 100%, MRR 0.95 (docs only).

## Findings

1. **Support cases crowd out articles for symptom-style questions.** Filtering to articles and release notes raised hit@5 from 90% to 100% and MRR from 0.85 to 0.95.
   → Stage 5 agent design: search articles and release notes for "how do I fix" questions; search support cases for "has this happened before" questions.
2. **Ranking uses the whole document, not just the title.** KB-1005's body mentions both "replacement" and "access point," so it keeps matching s09 ("replacement for a dead access point") regardless of title changes.
3. **Fixes can cause regressions.** Changing one title improved one query and hurt another, so the full eval set must be rerun after every change.
4. **Write titles in customers' words.** "RMA" is internal jargon; "replacing a failed or dead device" is how people ask.

## Decision

Stopped tuning at MRR 0.95. Further edits would mean rewriting document bodies to win a 10-query test, which is overfitting to the eval set rather than improving search for real users. The agent receives the top 5 results, so KB-1010 at rank 2 still reaches it.