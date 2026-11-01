-- Credits per day for everything this project runs, in one place:
--   agent         token credits per agent
--   search        serving / embedding / batch credits per search service
--   warehouse     compute credits per project warehouse (also covers SQL the agent runs)
with agent as (
    select
        date(start_time)                       as usage_date,
        'agent'                                as cost_category,
        agent_name                             as object_name,
        'tokens'                               as consumption_type,
        sum(token_credits)                     as credits,
        count(*)                               as requests
    from {{ source('snowflake_usage', 'cortex_agent_usage_history') }}
    where agent_database_name = '{{ target.database }}'
    group by 1, 2, 3, 4
),

search as (
    select
        usage_date,
        'search',
        service_name,
        lower(consumption_type),
        sum(credits),
        null
    from {{ source('snowflake_usage', 'cortex_search_daily_usage_history') }}
    where database_name = '{{ target.database }}'
    group by 1, 2, 3, 4
),

warehouse as (
    select
        date(start_time),
        'warehouse',
        warehouse_name,
        'compute',
        sum(credits_used),
        null
    from {{ source('snowflake_usage', 'warehouse_metering_history') }}
    where warehouse_name like 'NOI_WH_%'
    group by 1, 2, 3, 4
)

select * from agent
union all select * from search
union all select * from warehouse
