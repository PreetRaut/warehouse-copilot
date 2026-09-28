{{
  config(
    materialized='incremental',
    unique_key='fx_rate_key',
    incremental_strategy='merge'
  )
}}

with enriched as (
    select * from {{ ref('int_fx_rates_enriched') }}
    {% if is_incremental() %}
      where rate_date > (select coalesce(max(rate_date), '1900-01-01') from {{ this }})
    {% endif %}
)

select
    {{ dbt_utils.generate_surrogate_key(['rate_date', 'base_currency', 'quote_currency']) }}
        as fx_rate_key,
    rate_date,
    base_currency,
    quote_currency,
    quote_currency_name,
    quote_region,
    rate,
    loaded_at
from enriched
