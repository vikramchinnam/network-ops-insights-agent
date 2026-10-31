select
    customer_id,
    customer_name,
    industry,
    region,
    partner_id,
    contract_tier,
    created_at::date as customer_since
from {{ source('raw', 'customers') }}
