# Stage 3 — Cortex Analyst scorecard

Semantic view: `NOI_DEV.SEMANTIC.NETWORK_OPS_ANALYTICS` · Date run: YYYY-MM-DD

Mark each answer **Correct** (same numbers as the reference SQL), **Partly** (right idea, wrong filter or grouping), or **Wrong**. For anything not Correct, note what you changed in the semantic view.

# Stage 3 — Cortex Analyst scorecard

Semantic view: `NOI_DEV.SEMANTIC.NETWORK_OPS_ANALYTICS` · Date run: 2026-10-31

| ID | Question (short) | Run 1 | Fix made | Run 2 |
| --- | --- | --- | --- | --- |
| q01 | Roaming failures by AP firmware | Correct — 10.2.1 ≈ 8.0/day vs ≈ 2.0 | — | — |
| q02 | Uptime by industry, last 30 days | Correct | — | — |
| q03 | Open critical cases by industry | Correct — used P1+P2 | — | — |
| q04 | Top 5 customers by open cases | Correct | — | — |
| q05 | Time to resolve by severity | Partly — included open cases as 0 hrs | Added "exclude open cases" to metric COMMENT | Correct |
| q06 | End of sale in 12 months, by model | Correct — only AX-200 | — | — |
| q07 | Renewing contract value by partner | Correct | — | — |
| q08 | Top 10 sites by disconnects, 7 days | Partly — used 8 days (>= vs >) | Clarified "last 7 days" in AI_SQL_GENERATION | Correct |
| q09 | Cases by category, last 30 days | Correct | — | — |
| q10 | Renewals with open critical cases | Correct | — | — |
| q11 | Which hospitals have the worst Wi-Fi?| Partly - using incorrect formula|Clarified "Worst Wi-Fi means the highest roaming plus authentication failures per access point." in AI_SQL_GENERATION | Correct |

**Score:** Run 1 8/11 · Run 2 11/11

**What I learned:**
- Most misses were date-boundary or business-definition issues, not join problems.
- Fixing comments and instructions improved accuracy without changing any tables.