{# Use the schema configured on each model as-is (no dev-name prefixing),
   so RAW / ANALYTICS stay predictable for the MCP server to query. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
