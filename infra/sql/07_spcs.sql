-- =====================================================================
-- 07_spcs.sql — Snowpark Container Services setup (Stage 7). Run as ACCOUNTADMIN.
--
--   NOI_SPCS        owns the image repository and the service; nothing else
--   NOI_POOL        X-Small compute pool, created SUSPENDED (no cost until a service starts)
--   NOI_DEV.SPCS    schema for the image repository and the service
--   caller grants   which of the SIGNED-IN USER's privileges the app may use (caller's rights)
--
-- Rerunnable. Section 5 uses newer object types; if one of those lines errors, run the rest
-- and tell me which line failed.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- 1. Service owner role
CREATE ROLE IF NOT EXISTS NOI_SPCS COMMENT = 'Network Ops Insights: owns the container service';
GRANT ROLE NOI_SPCS TO ROLE NOI_ADMIN;
SET my_user = CURRENT_USER();
GRANT ROLE NOI_SPCS TO USER IDENTIFIER($my_user);
GRANT BIND SERVICE ENDPOINT ON ACCOUNT TO ROLE NOI_SPCS;   -- needed for a public endpoint

-- 2. Compute pool: smallest size, auto-suspends after 10 idle minutes
CREATE COMPUTE POOL IF NOT EXISTS NOI_POOL
  MIN_NODES = 1
  MAX_NODES = 1
  INSTANCE_FAMILY = CPU_X64_XS
  AUTO_RESUME = TRUE
  AUTO_SUSPEND_SECS = 600
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Network Ops Insights: chat app (dev)';
GRANT USAGE, MONITOR, OPERATE ON COMPUTE POOL NOI_POOL TO ROLE NOI_SPCS;

-- 3. Schema, compute and the image repository
CREATE SCHEMA IF NOT EXISTS NOI_DEV.SPCS;
GRANT OWNERSHIP ON SCHEMA NOI_DEV.SPCS TO ROLE NOI_SPCS COPY CURRENT GRANTS;
GRANT USAGE ON DATABASE NOI_DEV TO ROLE NOI_SPCS;
GRANT USAGE ON WAREHOUSE NOI_WH_DEV TO ROLE NOI_SPCS;

USE ROLE NOI_SPCS;
CREATE IMAGE REPOSITORY IF NOT EXISTS NOI_DEV.SPCS.IMAGES;
USE ROLE ACCOUNTADMIN;

-- 4. Caller grants: the app can act as the signed-in user ONLY within these privileges.
--    The user still needs the privilege themselves; caller grants are an upper bound,
--    so a partner's row access policy and grants still apply.
GRANT CALLER USAGE ON DATABASE NOI_DEV TO ROLE NOI_SPCS;
GRANT CALLER USAGE ON WAREHOUSE NOI_WH_DEV TO ROLE NOI_SPCS;
GRANT INHERITED CALLER USAGE ON ALL SCHEMAS IN DATABASE NOI_DEV TO ROLE NOI_SPCS;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN DATABASE NOI_DEV TO ROLE NOI_SPCS;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN DATABASE NOI_DEV TO ROLE NOI_SPCS;

-- 5. Caller grants for the objects the agent uses
GRANT INHERITED CALLER SELECT, REFERENCES ON ALL SEMANTIC VIEWS IN DATABASE NOI_DEV TO ROLE NOI_SPCS;
GRANT INHERITED CALLER USAGE ON ALL CORTEX SEARCH SERVICES IN DATABASE NOI_DEV TO ROLE NOI_SPCS;
GRANT INHERITED CALLER USAGE ON ALL AGENTS IN DATABASE NOI_DEV TO ROLE NOI_SPCS;

-- Check what was granted
SHOW CALLER GRANTS TO ROLE NOI_SPCS;
