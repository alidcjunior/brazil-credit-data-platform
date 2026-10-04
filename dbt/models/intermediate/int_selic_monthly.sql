-- Meta Selic (série 432, diária) agregada por mês: média e valor do último dia disponível.
with selic as (
    select ref_date, value
    from {{ ref('stg_bcb_sgs__observations') }}
    where series_code = 432
)

select
    date_trunc('month', ref_date)::date as ref_month,
    round(avg(value), 4) as selic_target_avg,
    (array_agg(value order by ref_date desc))[1] as selic_target_eom
from selic
group by 1
