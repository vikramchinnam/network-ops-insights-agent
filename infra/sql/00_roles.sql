-- =====================================================================
-- 00_roles.sql — Role hierarchy (run as SECURITYADMIN)
--
--   SYSADMIN
--     └── NOI_ADMIN            project owner, used by you for setup
--           ├── NOI_DBT_DEV     builds dbt models in NOI_DEV
--           ├── NOI_DBT_PROD    builds dbt models in NOI_PROD (CI only)
--           └── NOI_AGENT_USER  asks the agent questions; read-only
--
-- Why: never use ACCOUNTADMIN for daily work. Each job gets the
-- smallest role that can do it. Rerunnable (IF NOT EXISTS).
-- =====================================================================
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS NOI_ADMIN      COMMENT = 'Network Ops Insights: project admin';
CREATE ROLE IF NOT EXISTS NOI_DBT_DEV    COMMENT = 'Network Ops Insights: dbt in Dev';
CREATE ROLE IF NOT EXISTS NOI_DBT_PROD   COMMENT = 'Network Ops Insights: dbt in Prod (CI only)';
CREATE ROLE IF NOT EXISTS NOI_AGENT_USER COMMENT = 'Network Ops Insights: agent consumers (read-only)';

-- Hierarchy: functional roles roll up to NOI_ADMIN, which rolls up to SYSADMIN
GRANT ROLE NOI_DBT_DEV    TO ROLE NOI_ADMIN;
GRANT ROLE NOI_DBT_PROD   TO ROLE NOI_ADMIN;
GRANT ROLE NOI_AGENT_USER TO ROLE NOI_ADMIN;
GRANT ROLE NOI_ADMIN      TO ROLE SYSADMIN;

-- Give yourself the project roles
SET my_user = CURRENT_USER();
GRANT ROLE NOI_ADMIN   TO USER IDENTIFIER($my_user);
GRANT ROLE NOI_DBT_DEV TO USER IDENTIFIER($my_user);
