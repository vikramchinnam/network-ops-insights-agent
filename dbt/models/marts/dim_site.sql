-- One row per site, with its customer's industry and partner for filtering.
select
    s.site_id,
    s.site_name,
    s.site_type,
    s.city,
    s.country,
    s.customer_id,
    c.customer_name,
    c.industry,
    c.partner_id
from {{ ref('stg_sites') }} s
join {{ ref('stg_customers') }} c on s.customer_id = c.customer_id
