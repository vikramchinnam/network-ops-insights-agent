-- One row per agent request in this environment's database: who asked, as which role, through
-- which interface, how long it took, and what it cost. Feeds the Stage 7 observability page.
select
    request_id,
    start_time,
    end_time,
    datediff(millisecond, start_time, end_time) / 1000.0         as duration_s,
    agent_name,
    agent_database_name || '.' || agent_schema_name || '.' || agent_name as agent_fqn,
    user_name,
    metadata:role_name::varchar                                  as role_name,
    metadata:interaction_interface::varchar                      as interface,
    tokens,
    token_credits                                                as credits
from {{ source('snowflake_usage', 'cortex_agent_usage_history') }}
where agent_database_name = '{{ target.database }}'
