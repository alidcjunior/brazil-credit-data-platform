-- A série precisa começar exatamente no início do período de análise.
select min(ref_month) as first_month
from {{ ref('fct_monthly_macro_indicators') }}
having min(ref_month) is null
    or min(ref_month) <> '{{ var("analysis_start") }}'::date
