-- One row per support case.
select
    sc.case_id,
    sc.customer_id,
    c.partner_id,
    c.industry,
    sc.site_id,
    sc.device_id,
    sc.opened_at,
    sc.closed_at,
    sc.opened_at::date                                         as opened_date,
    sc.status,
    sc.status = 'Open'                                         as is_open,
    sc.severity,
    sc.severity in ('P1', 'P2')                                as is_critical,
    sc.category,
    sc.product_model,
    sc.firmware_version,
    datediff(minute, sc.opened_at, sc.closed_at) / 60.0       as resolution_hours,
    sc.subject,
    sc.description
from {{ ref('stg_support_cases') }} sc
join {{ ref('stg_customers') }} c on sc.customer_id = c.customer_id
