-- =====================================================================
-- 03_cost_guardrails.sql — Resource monitor (run as ACCOUNTADMIN)
--
-- Caps warehouse spend at 40 credits a month:
--   75%  → email notification
--   90%  → suspend warehouses after running queries finish
--   100% → suspend immediately, cancelling running queries
--
-- IMPORTANT: resource monitors cover WAREHOUSES only. Cortex (Agents,
-- Analyst, Search) and Container Services compute pools are NOT capped
-- by this. Watch those with 91_cost_report.sql and 99_teardown.sql.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE RESOURCE MONITOR NOI_MONTHLY_CAP
  WITH CREDIT_QUOTA = 40
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 75  PERCENT DO NOTIFY
    ON 90  PERCENT DO SUSPEND
    ON 100 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE NOI_WH_DEV  SET RESOURCE_MONITOR = NOI_MONTHLY_CAP;
ALTER WAREHOUSE NOI_WH_PROD SET RESOURCE_MONITOR = NOI_MONTHLY_CAP;
