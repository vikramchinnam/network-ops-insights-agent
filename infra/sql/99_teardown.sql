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

-- Cortex Search services keep billing while they exist (Stage 4)
-- DROP CORTEX SEARCH SERVICE IF EXISTS NOI_DEV.SEARCH.SUPPORT_DOCS;
-- DROP CORTEX SEARCH SERVICE IF EXISTS NOI_PROD.SEARCH.SUPPORT_DOCS;

-- Container Services compute pool (Stage 7)
-- ALTER COMPUTE POOL IF EXISTS NOI_POOL STOP ALL;
-- ALTER COMPUTE POOL IF EXISTS NOI_POOL SUSPEND;
