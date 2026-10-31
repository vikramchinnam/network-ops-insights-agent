-- =====================================================================
-- 01_warehouses.sql — Compute (run as SYSADMIN)
--
-- Cost rules baked in:
--   * X-SMALL = 1 credit/hour, billed only while running
--   * AUTO_SUSPEND = 60 seconds of idle time
--   * STATEMENT_TIMEOUT stops runaway queries after 10 minutes
--   * INITIALLY_SUSPENDED so creating them costs nothing
-- =====================================================================
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS NOI_WH_DEV
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  STATEMENT_TIMEOUT_IN_SECONDS = 600
  COMMENT = 'Network Ops Insights: Dev + CI';

CREATE WAREHOUSE IF NOT EXISTS NOI_WH_PROD
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  STATEMENT_TIMEOUT_IN_SECONDS = 600
  COMMENT = 'Network Ops Insights: Prod + agent queries';

GRANT USAGE ON WAREHOUSE NOI_WH_DEV  TO ROLE NOI_DBT_DEV;
GRANT USAGE ON WAREHOUSE NOI_WH_PROD TO ROLE NOI_DBT_PROD;
GRANT USAGE ON WAREHOUSE NOI_WH_PROD TO ROLE NOI_AGENT_USER;
GRANT ALL   ON WAREHOUSE NOI_WH_DEV  TO ROLE NOI_ADMIN;
GRANT ALL   ON WAREHOUSE NOI_WH_PROD TO ROLE NOI_ADMIN;
