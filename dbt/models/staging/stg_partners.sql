select
    partner_id,
    partner_name,
    partner_type,
    region as partner_region
from {{ source('raw', 'partners') }}
