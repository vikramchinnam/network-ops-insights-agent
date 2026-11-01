-- depends_on: {{ ref('tenant_access') }}  (row access policy must exist before this table is secured)
-- One row per customer, with partner details and footprint counts.
with sites as (
    select customer_id, count(*) as site_count
    from {{ ref('stg_sites') }}
    group by 1
),

devices as (
    select
        s.customer_id,
        count(*)                                                    as device_count,
        count_if(d.device_type = 'access_point')                    as access_point_count,
        count_if(d.device_type = 'switch')                          as switch_count
    from {{ ref('stg_devices') }} d
    join {{ ref('stg_sites') }} s on d.site_id = s.site_id
    group by 1
)

select
    c.customer_id,
    c.customer_name,
    c.industry,
    c.region,
    c.contract_tier,
    c.customer_since,
    c.partner_id,
    p.partner_name,
    p.partner_type,
    coalesce(s.site_count, 0)          as site_count,
    coalesce(d.device_count, 0)        as device_count,
    coalesce(d.access_point_count, 0)  as access_point_count,
    coalesce(d.switch_count, 0)        as switch_count
from {{ ref('stg_customers') }} c
left join {{ ref('stg_partners') }} p on c.partner_id = p.partner_id
left join sites s   on c.customer_id = s.customer_id
left join devices d on c.customer_id = d.customer_id
