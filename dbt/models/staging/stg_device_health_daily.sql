select
    device_id,
    metric_date::date      as metric_date,
    uptime_pct,
    cpu_pct,
    client_count,
    disconnect_count,
    auth_failure_count,       -- NULL for switches (Wi-Fi metric)
    roaming_failure_count     -- NULL for switches (Wi-Fi metric)
from {{ source('raw', 'device_health_daily') }}
