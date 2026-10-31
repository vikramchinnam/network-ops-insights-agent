{#
  Where does a model land?
    dev / prod : the folder's schema as-is      -> NOI_DEV.MARTS, NOI_PROD.MARTS
    ci         : prefixed per pull request       -> NOI_DEV.PR_12_MARTS
  Dev and Prod are already isolated by database, so no prefix is needed there.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- elif target.name == 'ci' -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
