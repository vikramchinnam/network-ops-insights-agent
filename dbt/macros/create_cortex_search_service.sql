{#
  Creates (or replaces) a Cortex Search service over the model it is attached to.
  Used as a post-hook, so the service is rebuilt every time dbt rebuilds the table.
  The warehouse comes from the dbt target, so Dev and Prod each use their own.

  Why replace on every build: dbt recreates the source table, and the service must
  point at the new table. The document set is small, so re-indexing is cheap.
#}
{% macro create_cortex_search_service(service_name, search_column, attributes, target_lag='1 day') %}
    create or replace cortex search service {{ this.database }}.{{ this.schema }}.{{ service_name }}
        on {{ search_column }}
        attributes {{ attributes | join(', ') }}
        warehouse = {{ target.warehouse }}
        target_lag = '{{ target_lag }}'
        comment = 'Support cases, knowledge base articles and release notes (built by dbt)'
    as (
        select * from {{ this }}
    )
{% endmacro %}
