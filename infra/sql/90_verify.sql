-- =====================================================================
-- 90_verify.sql — Checks that Stage 1 setup worked (run as NOI_ADMIN)
-- =====================================================================
USE ROLE NOI_ADMIN;

SHOW ROLES      LIKE 'NOI%';
SHOW WAREHOUSES LIKE 'NOI%';
SHOW DATABASES  LIKE 'NOI%';

-- Should return one row from the Dev warehouse
USE WAREHOUSE NOI_WH_DEV;
SELECT CURRENT_USER() AS who, CURRENT_ROLE() AS role, CURRENT_WAREHOUSE() AS wh, CURRENT_REGION() AS region;

-- Cortex smoke test: should return a short sentence.
-- New accounts must use AI_COMPLETE; legacy SNOWFLAKE.CORTEX.COMPLETE is blocked.
SELECT AI_COMPLETE('claude-haiku-4-5', 'Say hello to a network engineer in one sentence.') AS cortex_ok;
