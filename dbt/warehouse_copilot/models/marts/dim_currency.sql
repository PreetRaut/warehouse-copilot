-- Currency dimension, sourced from a version-controlled seed.
select
    currency_code,
    currency_name,
    region
from {{ ref('dim_currency_seed') }}
