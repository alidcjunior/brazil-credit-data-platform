-- IPCA (série 433, mensal) com acumulado em 12 meses composto.
-- A janela é por intervalo de datas: só há acumulado quando os 12 meses estão presentes.
with ipca as (
    select
        date_trunc('month', ref_date)::date as ref_month,
        value as ipca_mom
    from {{ ref('stg_bcb_sgs__observations') }}
    where series_code = 433
),

windowed as (
    select
        ref_month,
        ipca_mom,
        count(*) over last_12_months as months_in_window,
        exp(sum(ln(1 + ipca_mom / 100)) over last_12_months) as factor_12m
    from ipca
    window last_12_months as (
        order by ref_month
        range between interval '11 months' preceding and current row
    )
)

select
    ref_month,
    ipca_mom,
    case when months_in_window = 12 then round((factor_12m - 1) * 100, 4) end as ipca_12m
from windowed
