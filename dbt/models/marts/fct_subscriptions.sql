-- One row per subscription. Renewal flags are relative to the day the model is built.
select
    sub.subscription_id,
    sub.customer_id,
    c.partner_id,
    c.industry,
    sub.product,
    sub.term_years,
    sub.start_date,
    sub.end_date,
    sub.annual_value_usd,
    datediff(day, current_date(), sub.end_date)                             as days_to_renewal,
    sub.end_date < current_date()                                           as is_expired,
    sub.end_date between current_date() and dateadd(day, 90, current_date()) as is_renewing_within_90_days
from {{ ref('stg_subscriptions') }} sub
join {{ ref('stg_customers') }} c on sub.customer_id = c.customer_id
