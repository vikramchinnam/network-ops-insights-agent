-- Singular test: returns rows that break the rule. Zero rows = pass.
select device_id, metric_date, uptime_pct
from {{ ref('fct_device_health_daily') }}
where uptime_pct < 0 or uptime_pct > 100
