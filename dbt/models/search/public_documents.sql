{{
  config(
    post_hook=[
      "{{ create_cortex_search_service(
            service_name='PUBLIC_DOCS',
            search_column='content',
            attributes=['doc_type', 'category', 'product_models', 'firmware_version'],
            comment='KB articles and release notes only. Safe for partner roles.'
         ) }}"
    ]
  )
}}

{#
  Public documents only: knowledge base articles and release notes, no support cases.

  Why a separate table and search service instead of a filter on SUPPORT_DOCS:
  a filter in an agent spec only constrains that agent. A partner role with USAGE on
  SUPPORT_DOCS could query it directly and read other customers' case text. Partners
  get USAGE on PUBLIC_DOCS only, so the boundary is enforced by grants, not by prompts.
#}

select
    doc_id,
    doc_type,
    title,
    content,
    category,
    product_models,
    firmware_version,
    published_date
from {{ ref('search_documents') }}
where doc_type in ('kb_article', 'release_note')
