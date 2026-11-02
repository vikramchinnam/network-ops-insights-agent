-- =====================================================================
-- 99_teardown.sql — Stop spending (run as ACCOUNTADMIN)
--
-- Run this whenever you step away for more than a day.
-- Uncomment sections as later stages create those objects.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- Warehouses (Stage 1)
ALTER WAREHOUSE IF EXISTS NOI_WH_DEV  SUSPEND;
ALTER WAREHOUSE IF EXISTS NOI_WH_PROD SUSPEND;

-- Cortex Search services keep billing while they exist (Stage 4).
-- Suspending stops indexing and serving; dbt build recreates the service.
ALTER CORTEX SEARCH SERVICE IF EXISTS NOI_DEV.SEARCH.SUPPORT_DOCS SUSPEND INDEXING;
ALTER CORTEX SEARCH SERVICE IF EXISTS NOI_DEV.SEARCH.SUPPORT_DOCS SUSPEND SERVING;
ALTER CORTEX SEARCH SERVICE IF EXISTS NOI_DEV.SEARCH.PUBLIC_DOCS SUSPEND INDEXING;
ALTER CORTEX SEARCH SERVICE IF EXISTS NOI_DEV.SEARCH.PUBLIC_DOCS SUSPEND SERVING;
-- To remove it entirely:
-- DROP CORTEX SEARCH SERVICE IF EXISTS NOI_DEV.SEARCH.SUPPORT_DOCS;
-- DROP CORTEX SEARCH SERVICE IF EXISTS NOI_DEV.SEARCH.PUBLIC_DOCS;
-- DROP CORTEX SEARCH SERVICE IF EXISTS NOI_PROD.SEARCH.SUPPORT_DOCS;

-- Scheduled procedures (Stage 6): stop the schedules
ALTER TASK IF EXISTS NOI_DEV.OPS.TASK_CUSTOMER_HEALTH SUSPEND;
ALTER TASK IF EXISTS NOI_DEV.OPS.TASK_AGENT_EVAL SUSPEND;

-- Container Services (Stage 7): the pool bills while it is running, even when idle.
-- Suspending the service and the pool stops that; `deploy_service.py deploy` or
-- ALTER SERVICE ... RESUME brings it back (the pool auto-resumes).
ALTER SERVICE IF EXISTS NOI_DEV.SPCS.NOI_APP SUSPEND;
ALTER COMPUTE POOL IF EXISTS NOI_POOL SUSPEND;
-- To remove everything:
-- DROP SERVICE IF EXISTS NOI_DEV.SPCS.NOI_APP;
-- DROP COMPUTE POOL IF EXISTS NOI_POOL;
