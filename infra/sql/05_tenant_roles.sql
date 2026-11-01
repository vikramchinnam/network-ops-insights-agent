-- =====================================================================
-- 05_tenant_roles.sql — Persona roles for multi-tenant access (Stage 5B)
--
--   NOI_SUPPORT            internal support / customer success: sees everything
--   NOI_PARTNER_PTR_001    partner PTR-001: sees only its own customers
--   NOI_PARTNER_PTR_002    partner PTR-002: sees only its own customers
--
-- Which partner a role may see lives in dbt/seeds/tenant_access.csv, not here,
-- so access changes go through a reviewed pull request.
-- Object grants (tables, semantic view, search, agents) are applied by dbt and
-- deploy_agent.py, because those objects are recreated on each build.
-- Rerunnable.
-- =====================================================================
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS NOI_SUPPORT         COMMENT = 'Network Ops Insights: internal support (all tenants)';
CREATE ROLE IF NOT EXISTS NOI_PARTNER_PTR_001 COMMENT = 'Network Ops Insights: partner PTR-001 (own tenants only)';
CREATE ROLE IF NOT EXISTS NOI_PARTNER_PTR_002 COMMENT = 'Network Ops Insights: partner PTR-002 (own tenants only)';

-- Keep the hierarchy tidy: every custom role rolls up to NOI_ADMIN -> SYSADMIN
GRANT ROLE NOI_SUPPORT         TO ROLE NOI_ADMIN;
GRANT ROLE NOI_PARTNER_PTR_001 TO ROLE NOI_ADMIN;
GRANT ROLE NOI_PARTNER_PTR_002 TO ROLE NOI_ADMIN;

-- You test as each persona, so grant them to yourself
SET my_user = CURRENT_USER();
GRANT ROLE NOI_SUPPORT         TO USER IDENTIFIER($my_user);
GRANT ROLE NOI_PARTNER_PTR_001 TO USER IDENTIFIER($my_user);
GRANT ROLE NOI_PARTNER_PTR_002 TO USER IDENTIFIER($my_user);

-- Compute: the agent runs SQL on these warehouses as the caller's role
USE ROLE SYSADMIN;
GRANT USAGE ON WAREHOUSE NOI_WH_DEV  TO ROLE NOI_SUPPORT;
GRANT USAGE ON WAREHOUSE NOI_WH_PROD TO ROLE NOI_SUPPORT;
GRANT USAGE ON WAREHOUSE NOI_WH_DEV  TO ROLE NOI_PARTNER_PTR_001;
GRANT USAGE ON WAREHOUSE NOI_WH_PROD TO ROLE NOI_PARTNER_PTR_001;
GRANT USAGE ON WAREHOUSE NOI_WH_DEV  TO ROLE NOI_PARTNER_PTR_002;
GRANT USAGE ON WAREHOUSE NOI_WH_PROD TO ROLE NOI_PARTNER_PTR_002;

-- Cortex access for the personas
USE ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NOI_SUPPORT;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NOI_PARTNER_PTR_001;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NOI_PARTNER_PTR_002;
