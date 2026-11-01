-- One row per agent eval run (from the RUN_AGENT_EVAL procedure): quality over time.
select
    run_id,
    min(run_at)                                        as run_at,
    any_value(agent_name)                              as agent_name,
    count(*)                                           as questions,
    count_if(routing_ok)                               as routing_passed,
    count_if(facts_ok)                                 as facts_passed,
    count_if(routing_ok and facts_ok)                  as fully_correct,
    round(count_if(routing_ok and facts_ok) / nullif(count(*), 0), 3) as fully_correct_rate,
    count_if(error is not null)                        as errors,
    round(avg(latency_ms) / 1000.0, 1)                 as avg_latency_s,
    round(max(latency_ms) / 1000.0, 1)                 as max_latency_s
from {{ source('ops', 'agent_eval_runs') }}
group by run_id
