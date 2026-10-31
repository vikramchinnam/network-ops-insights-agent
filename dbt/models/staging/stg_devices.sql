select
    device_id,
    site_id,
    device_type,
    model,
    firmware_version,
    install_date::date     as install_date,
    end_of_sale_date::date as end_of_sale_date
from {{ source('raw', 'devices') }}
