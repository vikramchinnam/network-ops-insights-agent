select
    doc_id,
    title,
    product_models,
    firmware_version,
    category,
    published_date::date as published_date,
    body
from {{ source('raw', 'release_notes') }}
