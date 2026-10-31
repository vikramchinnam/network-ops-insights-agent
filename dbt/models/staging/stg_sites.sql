select
    site_id,
    customer_id,
    site_name,
    site_type,
    city,
    country
from {{ source('raw', 'sites') }}
