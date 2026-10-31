select
    subscription_id,
    customer_id,
    product,
    term_years,
    start_date::date as start_date,
    end_date::date   as end_date,
    annual_value_usd
from {{ source('raw', 'subscriptions') }}
