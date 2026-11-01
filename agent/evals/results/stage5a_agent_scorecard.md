# Stage 5A — Cortex Agent scorecard

Agent: `NOI_DEV.AGENTS.NETWORK_OPS_AGENT` · Orchestration model: claude-sonnet-4-5 · Date run: 2026-10-31

| ID | Question (short) | Expected tools | Run 1 | Fix | Run 2 |
| --- | --- | --- | --- | --- | --- |
| a01 | Roaming failures by firmware | NetworkMetrics | pass / pass | — | pass / pass |
| a02 | Known fix for 10.2.1 roaming | KnowledgeBase | pass / FAIL (no "KB-1001") | Agent: "always write the document ID" in response instructions | pass / pass |
| a03 | Why hospitals see roaming problems + what to do | NetworkMetrics, KnowledgeBase | pass / pass | — | pass / pass |
| a04 | 802.1X timeouts reported | CaseHistory | pass / pass | — | pass / pass (now also uses KnowledgeBase) |
| a05 | Open critical cases by industry | NetworkMetrics | pass / pass | — | pass / pass |
| a06 | AX-200 replacement + end of sale | KnowledgeBase | pass / FAIL (no "2026-12-31") | Eval: accept common date formats | pass / pass |
| a07 | Renewals with open critical cases + what they're about | NetworkMetrics, CaseHistory | FAIL / pass (skipped CaseHistory) | Agent: use CaseHistory for case descriptions | pass / pass |
| a08 | Off-topic (banana bread) | none | pass / pass | — | pass / pass |

Results shown as routing / facts.

**Totals:** Run 1: routing 7/8 · facts 6/8 · fully correct 5/8 → Run 2: 8/8 · 8/8 · 8/8

**Findings**
- Two of three failures were agent instructions that were too soft (citing IDs, fetching case descriptions); one was an eval check that was too literal (date format). Separating agent errors from eval errors avoided "fixing" correct behavior.
- The agent added built-in tools (data_to_chart) on its own for numeric answers; routing checks use "expected tools are a subset of tools used" so this doesn't count as a failure.
- Instruction changes have side effects: a04 began also consulting KnowledgeBase. Beneficial here, but it's why the full eval is rerun after every change.