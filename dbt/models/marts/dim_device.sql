-- depends_on: {{ ref('tenant_access') }}  (row access policy must exist before this table is secured)
-- One row per device. End-of-sale flag is relative to the day the model is built.
select
    d.device_id,
    d.device_type,
    d.model,
    d.firmware_version,
    d.install_date,
    d.end_of_sale_date,
    d.end_of_sale_date <= dateadd(month, 12, current_date())   as is_end_of_sale_within_12_months,
    d.site_id,
    s.customer_id,
    s.partner_id
from {{ ref('stg_devices') }} d
join {{ ref('dim_site') }} s on d.site_id = s.site_id
