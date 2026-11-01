-- =====================================================================
-- 06_ops_privileges.sql — Privileges for procedures, tasks and observability (Stage 6)
-- Run as ACCOUNTADMIN. Rerunnable.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- Snowflake Tasks: the build roles own and run the scheduled procedures
GRANT EXECUTE TASK ON ACCOUNT TO ROLE NOI_DBT_DEV;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE NOI_DBT_PROD;

-- Observability models read SNOWFLAKE.ACCOUNT_USAGE (agent, search and warehouse usage).
-- IMPORTED PRIVILEGES is the simple option for a trial account. In production, prefer the
-- narrower SNOWFLAKE database roles (for example SNOWFLAKE.USAGE_VIEWER) where they cover the views.
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE NOI_DBT_DEV;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE NOI_DBT_PROD;
