-- =====================================================================
-- 04_cortex_access.sql — Cortex AI access (run as ACCOUNTADMIN)
--
-- Cross-region inference lets Cortex use models hosted in other
-- regions when your region doesn't have them. Without it, some
-- models and features may be unavailable in your trial region.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';

-- Cortex functions require the SNOWFLAKE.CORTEX_USER database role
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NOI_ADMIN;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NOI_DBT_DEV;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NOI_DBT_PROD;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NOI_AGENT_USER;

-- Lets NOI_ADMIN read usage views for 91_cost_report.sql
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE NOI_ADMIN;
