{#
  Multi-tenant security (Stage 5B)

  One row access policy, TENANT_POLICY, decides which rows a role sees, by partner_id:
    - roles in var('exempt_roles') see every row (internal support and the dbt build roles)
    - any other role sees rows whose partner_id is mapped to it in the tenant_access seed
    - everyone else sees nothing

  CURRENT_ROLE() is used on purpose instead of IS_ROLE_IN_SESSION(): with secondary roles,
  IS_ROLE_IN_SESSION would let a partner session inherit an exempt role and see everything.

  Wiring:
    seed tenant_access   post-hooks: create_tenant_policy, set_tenant_policy_body
    every mart           post-hooks: drop_tenant_policies, add_tenant_policy (on partner_id)
    on-run-end           grant_consumer_access: object grants for the persona roles
#}

{% macro tenant_policy_body(mapping_table) -%}
    current_role() in (
        {%- for r in var('exempt_roles') %}'{{ r }}'{% if not loop.last %}, {% endif %}{% endfor -%}
    )
    or exists (
        select 1
        from {{ mapping_table }} a
        where a.role_name = current_role()
          and a.partner_id = row_partner_id
    )
{%- endmacro %}

{% macro tenant_policy_fqn() -%}
    {%- set seed = ref('tenant_access') -%}
    {{ seed.database }}.{{ seed.schema }}.TENANT_POLICY
{%- endmacro %}

{# --- seed post-hooks: `this` is the tenant_access table --- #}
{% macro create_tenant_policy() %}
    create row access policy if not exists {{ this.database }}.{{ this.schema }}.TENANT_POLICY
        as (row_partner_id varchar) returns boolean ->
        {{ tenant_policy_body(this) }}
{% endmacro %}

{% macro set_tenant_policy_body() %}
    {# keeps the policy in sync with this file; CREATE OR REPLACE isn't allowed while it's attached #}
    alter row access policy {{ this.database }}.{{ this.schema }}.TENANT_POLICY
        set body -> {{ tenant_policy_body(this) }}
{% endmacro %}

{# --- mart post-hooks: `this` is the mart table --- #}
{% macro drop_tenant_policies() %}
    alter table {{ this }} drop all row access policies
{% endmacro %}

{% macro add_tenant_policy() %}
    alter table {{ this }} add row access policy {{ tenant_policy_fqn() }} on (partner_id)
{% endmacro %}

{# --- on-run-end: grants for the persona roles --- #}
{% macro grant_consumer_access() %}
    {% if not execute or target.name == 'ci' %}{{ return('select 1') }}{% endif %}

    {% set db = target.database %}
    {% set marts = generate_schema_name('marts', none) | trim %}
    {% set semantic = generate_schema_name('semantic', none) | trim %}
    {% set search = generate_schema_name('search', none) | trim %}

    {% set services = [] %}
    {% for row in run_query("show cortex search services in schema " ~ db ~ "." ~ search).rows %}
        {% do services.append(row['name'] | upper) %}
    {% endfor %}
    {% set has_sv = (run_query("show semantic views like 'NETWORK_OPS_ANALYTICS' in schema " ~ db ~ "." ~ semantic).rows | length) > 0 %}

    {% set roles = var('internal_roles') + var('partner_roles') %}
    {% for role in roles %}
        {% set stmts = [
            "grant usage on database " ~ db ~ " to role " ~ role,
            "grant usage on schema " ~ db ~ "." ~ marts ~ " to role " ~ role,
            "grant usage on schema " ~ db ~ "." ~ semantic ~ " to role " ~ role,
            "grant usage on schema " ~ db ~ "." ~ search ~ " to role " ~ role,
            "grant select on all tables in schema " ~ db ~ "." ~ marts ~ " to role " ~ role,
        ] %}
        {% if has_sv %}
            {% do stmts.append("grant select on semantic view " ~ db ~ "." ~ semantic ~ ".NETWORK_OPS_ANALYTICS to role " ~ role) %}
            {% do stmts.append("grant references on semantic view " ~ db ~ "." ~ semantic ~ ".NETWORK_OPS_ANALYTICS to role " ~ role) %}
        {% endif %}
        {% if 'PUBLIC_DOCS' in services %}
            {% do stmts.append("grant usage on cortex search service " ~ db ~ "." ~ search ~ ".PUBLIC_DOCS to role " ~ role) %}
        {% endif %}
        {# Only internal roles may search support cases, which contain customer-specific text #}
        {% if role in var('internal_roles') and 'SUPPORT_DOCS' in services %}
            {% do stmts.append("grant usage on cortex search service " ~ db ~ "." ~ search ~ ".SUPPORT_DOCS to role " ~ role) %}
        {% endif %}
        {% for s in stmts %}{% do run_query(s) %}{% endfor %}
    {% endfor %}
    {% do log("Granted consumer access to " ~ roles | join(", "), info=true) %}
    {{ return('select 1') }}
{% endmacro %}
