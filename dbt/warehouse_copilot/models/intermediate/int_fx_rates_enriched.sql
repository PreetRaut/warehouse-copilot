-- Join human-readable currency names onto the cleaned rates (ephemeral).
with rates as (
    select * from {{ ref('stg_fx_rates') }}
),
currencies as (
    select * from {{ ref('dim_currency') }}
)

select
    r.rate_date,
    r.base_currency,
    r.quote_currency,
    c.currency_name as quote_currency_name,
    c.region        as quote_region,
    r.rate,
    r.loaded_at
from rates r
left join currencies c
    on r.quote_currency = c.currency_code
