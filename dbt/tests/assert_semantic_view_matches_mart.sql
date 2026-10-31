-- The semantic view must give the same answer as querying the mart directly.
-- Catches wrong join paths or metric definitions before Cortex Analyst ever sees them.
with from_semantic_view as (
    select *
    from semantic_view(
        {{ ref('network_ops_analytics') }}
        dimensions devices.firmware_version
        metrics device_health.total_roaming_failures
    )
),

from_mart as (
    select
        d.firmware_version,
        sum(h.roaming_failure_count)  as total_roaming_failures
    from {{ ref('fct_device_health_daily') }} h
    join {{ ref('dim_device') }} d on h.device_id = d.device_id
    group by 1
)

select
    m.firmware_version,
    m.total_roaming_failures  as mart_value,
    s.total_roaming_failures  as semantic_view_value
from from_mart m
full outer join from_semantic_view s on m.firmware_version = s.firmware_version
where coalesce(m.total_roaming_failures, -1) <> coalesce(s.total_roaming_failures, -1)
