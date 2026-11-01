{{
  config(
    post_hook=[
      "{{ create_cortex_search_service(
            service_name='SUPPORT_DOCS',
            search_column='content',
            attributes=['doc_type', 'category', 'product_models', 'firmware_version',
                        'industry', 'customer_id', 'partner_id'],
            comment='Support cases, KB articles and release notes. Internal roles only.'
         ) }}"
    ]
  )
}}

{#
  One searchable table for every kind of text the agent should find.
  - content:      what Cortex Search indexes (title + body)
  - attributes:   columns you can filter on at query time
  - customer_id / partner_id: tenant keys. NULL for public documents (KB, release notes),
                  set for support cases. Used for tenant filtering in Stage 5.
#}

with kb as (
    select
        doc_id,
        'kb_article'        as doc_type,
        title,
        body,
        category,
        product_models,
        firmware_version,
        null::varchar       as industry,
        null::varchar       as customer_id,
        null::varchar       as partner_id,
        published_date
    from {{ ref('stg_kb_articles') }}
),

release_notes as (
    select
        doc_id,
        'release_note'      as doc_type,
        title,
        body,
        category,
        product_models,
        firmware_version,
        null, null, null,
        published_date
    from {{ ref('stg_release_notes') }}
),

cases as (
    select
        case_id                                                         as doc_id,
        'support_case'                                                  as doc_type,
        subject                                                         as title,
        description || ' Severity ' || severity || ', status ' || lower(status) || '.' as body,
        category,
        product_model                                                   as product_models,
        firmware_version,
        industry,
        customer_id,
        partner_id,
        opened_date                                                     as published_date
    from {{ ref('fct_support_cases') }}
),

unioned as (
    select * from kb
    union all
    select * from release_notes
    union all
    select * from cases
)

select
    doc_id,
    doc_type,
    title,
    title || '\n\n' || body as content,
    category,
    product_models,
    firmware_version,
    industry,
    customer_id,
    partner_id,
    published_date
from unioned
