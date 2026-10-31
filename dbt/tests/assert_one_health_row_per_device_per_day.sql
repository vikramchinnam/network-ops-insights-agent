-- Grain check for the fact table: device_id + metric_date must be unique.
select device_id, metric_date, count(*) as n
from {{ ref('fct_device_health_daily') }}
group by 1, 2
having count(*) > 1
