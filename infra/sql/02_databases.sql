-- =====================================================================
-- 02_databases.sql — One database per environment (run as SYSADMIN)
--
--   NOI_DEV   owned by NOI_DBT_DEV   (you build and break things here)
--   NOI_PROD  owned by NOI_DBT_PROD  (only CI deploys here, Stage 8)
--
-- The RAW schema holds synthetic source data. dbt creates the
-- STAGING, MARTS and SEMANTIC schemas itself in Stage 2.
-- =====================================================================
USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS NOI_DEV  COMMENT = 'Network Ops Insights: Dev';
CREATE DATABASE IF NOT EXISTS NOI_PROD COMMENT = 'Network Ops Insights: Prod';

CREATE SCHEMA IF NOT EXISTS NOI_DEV.RAW;
CREATE SCHEMA IF NOT EXISTS NOI_PROD.RAW;

-- Hand ownership to the environment's dbt role
GRANT OWNERSHIP ON SCHEMA   NOI_DEV.RAW  TO ROLE NOI_DBT_DEV  COPY CURRENT GRANTS;
GRANT OWNERSHIP ON DATABASE NOI_DEV      TO ROLE NOI_DBT_DEV  COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   NOI_PROD.RAW TO ROLE NOI_DBT_PROD COPY CURRENT GRANTS;
GRANT OWNERSHIP ON DATABASE NOI_PROD     TO ROLE NOI_DBT_PROD COPY CURRENT GRANTS;

-- Agent users can see Prod; table-level SELECT grants come in Stage 2–3
GRANT USAGE ON DATABASE NOI_PROD TO ROLE NOI_AGENT_USER;
