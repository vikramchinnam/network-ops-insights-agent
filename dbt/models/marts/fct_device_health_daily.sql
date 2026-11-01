-- depends_on: {{ ref('tenant_access') }}  (row access policy must exist before this table is secured)
-- One row per device per day. Grain: device_id + metric_date.
-- Simplification: firmware_version is the device's current version, not the version on that day.
select
    h.device_id,
    h.metric_date,
    d.device_type,
    d.model,
    d.firmware_version,
    d.site_id,
    d.customer_id,
    d.partner_id,
    h.uptime_pct,
    h.uptime_pct < 99                 as is_degraded_day,
    h.cpu_pct,
    h.client_count,
    h.disconnect_count,
    h.auth_failure_count,
    h.roaming_failure_count
from {{ ref('stg_device_health_daily') }} h
join {{ ref('dim_device') }} d on h.device_id = d.device_id
