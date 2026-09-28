with source as (
    select * from {{ source('raw', 'fx_rates') }}
)

select
    rate_date::date                          as rate_date,
    upper(base_currency)                     as base_currency,
    upper(quote_currency)                    as quote_currency,
    rate::float                              as rate,
    loaded_at::timestamp_ntz                 as loaded_at
from source
where rate is not null
  and rate > 0
