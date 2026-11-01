-- =====================================================================
-- 91_cost_report.sql — Where did the credits go? (run as NOI_ADMIN)
-- ACCOUNT_USAGE views lag by up to a few hours.
-- =====================================================================
USE ROLE NOI_ADMIN;
USE WAREHOUSE NOI_WH_DEV;

-- Credits by service type, last 30 days (warehouses, AI services, SPCS, ...)
SELECT service_type,
       ROUND(SUM(credits_used), 2) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
WHERE usage_date >= DATEADD(day, -30, CURRENT_DATE())
GROUP BY service_type
ORDER BY credits DESC;

-- Credits by warehouse, last 30 days
SELECT warehouse_name,
       ROUND(SUM(credits_used), 2) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY warehouse_name
ORDER BY credits DESC;

-- ---------------------------------------------------------------------
-- Cortex costs: NOT covered by the resource monitor, so check them here
-- ---------------------------------------------------------------------

-- Cortex Search: serving (continuous while the service exists) vs. indexing/embedding, last 30 days
SELECT usage_date,
       database_name || '.' || schema_name || '.' || service_name AS service,
       consumption_type,
       ROUND(SUM(credits), 4) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
WHERE usage_date >= DATEADD(day, -30, CURRENT_DATE())
GROUP BY 1, 2, 3
ORDER BY usage_date DESC, credits DESC;

-- Cortex Agents: tokens and credits per agent per day, with who asked, last 30 days
-- (Snowflake Intelligence / CoWork usage is in a separate view and not included here)
SELECT DATE(start_time)                                             AS usage_date,
       agent_database_name || '.' || agent_schema_name || '.' || agent_name AS agent,
       COUNT(*)                                                     AS requests,
       SUM(tokens)                                                  AS tokens,
       ROUND(SUM(token_credits), 4)                                 AS token_credits,
       ROUND(SUM(token_credits) / NULLIF(COUNT(*), 0), 5)           AS credits_per_request
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY usage_date DESC, token_credits DESC;
