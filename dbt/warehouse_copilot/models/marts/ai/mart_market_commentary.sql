-- OPTIONAL: native Snowflake AI enrichment.
-- Uses SNOWFLAKE.CORTEX.COMPLETE to generate a short natural-language commentary
-- on the latest metrics. Disabled by default so the core pipeline stays free and
-- portable. Enable with:  dbt build --vars '{enable_cortex: true}'
{{ config(enabled = var('enable_cortex', false)) }}

with latest as (
    select
        quote_currency,
        rate_date,
        round(rate, 4)         as rate,
        round(daily_return, 4) as daily_return,
        round(volatility_30, 4) as volatility_30
    from {{ ref('mart_fx_daily_metrics') }}
    qualify row_number() over (partition by quote_currency order by rate_date desc) = 1
),

payload as (
    select
        listagg(
            quote_currency || ': rate=' || rate ||
            ', daily_return=' || coalesce(daily_return, 0) ||
            ', vol30=' || coalesce(volatility_30, 0),
            '; '
        ) as facts,
        max(rate_date) as as_of
    from latest
)

select
    as_of,
    facts,
    snowflake.cortex.complete(
        'llama3.1-8b',
        'You are a markets analyst. In two sentences, summarise these EUR FX '
        || 'metrics for a non-technical reader. Data: ' || facts
    ) as commentary
from payload
