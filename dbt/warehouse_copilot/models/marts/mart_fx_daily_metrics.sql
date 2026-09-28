-- Analytical mart: per-currency daily returns, moving average and volatility.
-- Demonstrates window functions in Snowflake SQL.
with base as (
    select * from {{ ref('fct_fx_rate') }}
),

with_lag as (
    select
        *,
        lag(rate) over (
            partition by base_currency, quote_currency
            order by rate_date
        ) as prev_rate
    from base
),

with_return as (
    select
        *,
        case when prev_rate is not null and prev_rate <> 0
             then (rate / prev_rate) - 1
        end as daily_return
    from with_lag
)

select
    fx_rate_key,
    rate_date,
    base_currency,
    quote_currency,
    quote_currency_name,
    rate,
    daily_return,
    avg(rate) over (
        partition by base_currency, quote_currency
        order by rate_date
        rows between 6 preceding and current row
    ) as ma_7,
    avg(rate) over (
        partition by base_currency, quote_currency
        order by rate_date
        rows between 29 preceding and current row
    ) as ma_30,
    stddev(daily_return) over (
        partition by base_currency, quote_currency
        order by rate_date
        rows between 29 preceding and current row
    ) as volatility_30
from with_return
