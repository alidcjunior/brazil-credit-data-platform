-- Todos os meses entre o primeiro e o último precisam existir.
with bounds as (
    select min(ref_month) as first_month, max(ref_month) as last_month
    from {{ ref('fct_monthly_macro_indicators') }}
),

expected as (
    select generate_series(first_month, last_month, interval '1 month')::date as ref_month
    from bounds
)

select expected.ref_month
from expected
left join {{ ref('fct_monthly_macro_indicators') }} as fct
    on expected.ref_month = fct.ref_month
where fct.ref_month is null
