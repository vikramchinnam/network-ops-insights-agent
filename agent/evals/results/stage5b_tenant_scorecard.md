# Stage 5B — Multi-tenant security scorecard

Environment: `NOI_DEV` · Date run: YYYY-MM-DD · Command: `uv run python agent/evals/run_tenant_eval.py`

| Persona | Scope | tables (6) | semantic_view | search: PUBLIC_DOCS | search: SUPPORT_DOCS | agent probes (4) |
| --- | --- | --- | --- | --- | --- | --- |
| NOI_SUPPORT | all partners | | | allowed? | allowed? | |
| NOI_PARTNER_PTR_001 | PTR-001 | | | allowed? | denied? | |
| NOI_PARTNER_PTR_002 | PTR-002 | | | allowed? | denied? | |

**Total:** __/__ checks passed · Leaks found: __

**Internal agent regression check:** `run_agent_eval.py` → __/8 fully correct

**Findings:**
- In Snowsight, a user holding several roles sees both agents even with a partner role selected,
  because secondary roles are on by default. Not a leak: the tenant eval runs with
  `USE SECONDARY ROLES NONE` and passes. Production rule: partner users get exactly one role and
  `DEFAULT_SECONDARY_ROLES = ()`.
