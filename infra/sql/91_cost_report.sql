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
