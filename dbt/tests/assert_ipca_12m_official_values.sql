-- IPCA acumulado em 12 meses de dezembro = inflação oficial do ano (IBGE), tolerância 0,01 p.p.
with official (ref_month, ipca_12m) as (
    values
        (date '2015-12-01', 10.67),
        (date '2017-12-01', 2.95),
        (date '2021-12-01', 10.06)
)

select
    official.ref_month,
    official.ipca_12m as official_ipca_12m,
    fct.ipca_12m
from official
left join {{ ref('fct_monthly_macro_indicators') }} as fct
    on official.ref_month = fct.ref_month
where fct.ipca_12m is null
   or abs(fct.ipca_12m - official.ipca_12m) > 0.01
