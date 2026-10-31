{#
  Semantic view for Cortex Analyst: the business meaning of the marts.

  How to read it:
    TABLES         logical tables (aliases) over dbt marts, with primary keys and synonyms
    RELATIONSHIPS  how they join; the many side references the one side
    FACTS          row-level numbers that metrics aggregate
    DIMENSIONS     attributes you group and filter by
    METRICS        aggregations, the answers people ask for
  Synonyms and comments are what Cortex Analyst reads to map plain English to SQL,
  so they matter as much as the expressions.
#}

TABLES (
    customers AS {{ ref('dim_customer') }}
        PRIMARY KEY (customer_id)
        WITH SYNONYMS ('accounts', 'clients', 'end customers')
        COMMENT = 'One row per customer organization',

    sites AS {{ ref('dim_site') }}
        PRIMARY KEY (site_id)
        WITH SYNONYMS ('locations', 'facilities', 'buildings')
        COMMENT = 'One row per customer site such as a hospital, school or store',

    devices AS {{ ref('dim_device') }}
        PRIMARY KEY (device_id)
        WITH SYNONYMS ('network devices', 'hardware', 'access points', 'APs', 'switches')
        COMMENT = 'One row per access point or switch',

    device_health AS {{ ref('fct_device_health_daily') }}
        PRIMARY KEY (device_id, metric_date)
        WITH SYNONYMS ('telemetry', 'device metrics', 'network health')
        COMMENT = 'Daily health metrics, one row per device per day',

    cases AS {{ ref('fct_support_cases') }}
        PRIMARY KEY (case_id)
        WITH SYNONYMS ('support cases', 'tickets', 'support tickets', 'incidents')
        COMMENT = 'One row per support case',

    subscriptions AS {{ ref('fct_subscriptions') }}
        PRIMARY KEY (subscription_id)
        WITH SYNONYMS ('contracts', 'renewals', 'licenses')
        COMMENT = 'One row per customer subscription'
)

RELATIONSHIPS (
    sites_to_customers         AS sites (customer_id)         REFERENCES customers,
    devices_to_sites           AS devices (site_id)           REFERENCES sites,
    health_to_devices          AS device_health (device_id)   REFERENCES devices,
    cases_to_sites             AS cases (site_id)             REFERENCES sites,
    subscriptions_to_customers AS subscriptions (customer_id) REFERENCES customers
)

FACTS (
    device_health.uptime_pct             AS uptime_pct,
    device_health.client_count           AS client_count,
    device_health.disconnect_count       AS disconnect_count,
    device_health.roaming_failure_count  AS roaming_failure_count
        COMMENT = 'Failed client roams between access points; NULL for switches',
    device_health.auth_failure_count     AS auth_failure_count
        COMMENT = 'Failed client authentications; NULL for switches',
    cases.resolution_hours               AS resolution_hours,
    subscriptions.annual_value_usd       AS annual_value_usd,
    subscriptions.days_to_renewal        AS days_to_renewal
)

DIMENSIONS (
    customers.customer_name   AS customer_name   WITH SYNONYMS ('account name', 'customer'),
    customers.industry        AS industry        WITH SYNONYMS ('vertical', 'sector', 'segment'),
    customers.region          AS region,
    customers.contract_tier   AS contract_tier   WITH SYNONYMS ('support tier'),
    customers.partner_name    AS partner_name    WITH SYNONYMS ('partner', 'reseller', 'MSP'),
    customers.partner_type    AS partner_type,

    sites.site_name           AS site_name,
    sites.site_type           AS site_type       WITH SYNONYMS ('location type', 'facility type')
        COMMENT = 'Hospital, Clinic, Campus, Residence Hall, School, Plant, Warehouse, Store, Distribution Center, Hotel, Office, Library, Stadium or Arena',
    sites.city                AS city,
    sites.country             AS country,

    devices.device_type       AS device_type
        COMMENT = 'access_point or switch',
    devices.model             AS model           WITH SYNONYMS ('hardware model', 'device model'),
    devices.firmware_version  AS firmware_version WITH SYNONYMS ('firmware', 'software version', 'OS version'),
    devices.end_of_sale_date  AS end_of_sale_date WITH SYNONYMS ('EOS date', 'end of sale'),
    devices.is_end_of_sale_within_12_months AS is_end_of_sale_within_12_months,

    device_health.metric_date AS metric_date     WITH SYNONYMS ('date', 'day'),

    cases.opened_date         AS opened_date     WITH SYNONYMS ('case date', 'date opened'),
    cases.status              AS status
        COMMENT = 'Open or Closed',
    cases.severity            AS severity        WITH SYNONYMS ('priority')
        COMMENT = 'P1 (most severe) to P4',
    cases.category            AS category        WITH SYNONYMS ('issue type', 'case type', 'problem'),
        cases.case_product_model  AS product_model,
        cases.case_firmware_version AS firmware_version
        COMMENT = 'Firmware on the affected device when the case was opened',

    subscriptions.product     AS product,
    subscriptions.end_date    AS end_date        WITH SYNONYMS ('renewal date', 'expiration date'),
    subscriptions.is_renewing_within_90_days AS is_renewing_within_90_days
)

METRICS (
    customers.customer_count AS COUNT(customers.customer_id)
        WITH SYNONYMS ('number of customers'),

    devices.device_count AS COUNT(devices.device_id)
        WITH SYNONYMS ('number of devices', 'install base'),

    device_health.avg_uptime_pct AS AVG(device_health.uptime_pct)
        WITH SYNONYMS ('uptime', 'availability')
        COMMENT = 'Average daily uptime percentage, 0 to 100',
    device_health.degraded_device_days AS SUM(IFF(device_health.uptime_pct < 99, 1, 0))
        COMMENT = 'Device-days with uptime below 99 percent',
    device_health.total_disconnects AS SUM(device_health.disconnect_count)
        WITH SYNONYMS ('disconnects', 'drops'),
    device_health.total_roaming_failures AS SUM(device_health.roaming_failure_count)
        WITH SYNONYMS ('roaming failures', 'roaming problems'),
    device_health.avg_daily_roaming_failures AS AVG(device_health.roaming_failure_count)
        COMMENT = 'Average roaming failures per access point per day',
    device_health.total_auth_failures AS SUM(device_health.auth_failure_count)
        WITH SYNONYMS ('authentication failures', 'login failures', 'RADIUS failures'),

    cases.case_count AS COUNT(cases.case_id)
        WITH SYNONYMS ('number of cases', 'ticket count'),
    cases.open_case_count AS SUM(IFF(cases.status = 'Open', 1, 0))
        WITH SYNONYMS ('open tickets', 'backlog'),
    cases.open_critical_case_count AS SUM(IFF(cases.status = 'Open' AND cases.severity IN ('P1', 'P2'), 1, 0))
        WITH SYNONYMS ('open critical cases', 'open P1 and P2 cases')
        COMMENT = 'Critical means severity P1 or P2',
    cases.avg_resolution_hours AS AVG(cases.resolution_hours)
        WITH SYNONYMS ('MTTR', 'mean time to resolve', 'average resolution time'),

    subscriptions.total_annual_value_usd AS SUM(subscriptions.annual_value_usd)
        WITH SYNONYMS ('ARR', 'annual recurring revenue', 'contract value'),
    subscriptions.annual_value_renewing_90_days_usd AS SUM(IFF(subscriptions.is_renewing_within_90_days, subscriptions.annual_value_usd, 0))
        WITH SYNONYMS ('ARR up for renewal', 'renewing revenue', 'revenue at risk')
)

COMMENT = 'Network operations analytics for an enterprise networking customer base (synthetic data)'

AI_SQL_GENERATION 'Wi-Fi metrics (roaming and authentication failures) apply only to access points, so filter device_type to access_point when comparing them. "Critical" cases are severity P1 or P2. Relative dates such as "last week" refer to metric_date for device health and opened_date for cases. Round percentages and averages to 2 decimal places. Show currency in US dollars.Worst Wi-Fi means the highest roaming plus authentication failures per access point.'
