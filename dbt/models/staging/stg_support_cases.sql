select
    case_id,
    customer_id,
    site_id,
    device_id,
    opened_at,
    closed_at,
    status,
    severity,
    category,
    product_model,
    firmware_version,
    subject,
    description
from {{ source('raw', 'support_cases') }}
