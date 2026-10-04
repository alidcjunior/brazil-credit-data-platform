select
    series_code::integer as series_code,
    ref_date,
    value
from {{ source('silver', 'sgs_observation') }}
