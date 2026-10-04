-- Um mês por linha, do início da análise até o último mês com Selic e IPCA publicados.
select
    selic.ref_month,
    selic.selic_target_avg,
    selic.selic_target_eom,
    ipca.ipca_mom,
    ipca.ipca_12m
from {{ ref('int_selic_monthly') }} as selic
inner join {{ ref('int_ipca_monthly') }} as ipca
    on selic.ref_month = ipca.ref_month
where selic.ref_month >= '{{ var("analysis_start") }}'::date
