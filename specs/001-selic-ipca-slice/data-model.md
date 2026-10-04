# Data Model: Fatia 1 — Selic e IPCA ponta a ponta

## Catálogo de séries (configuração em código)

| series_code | name | unit | periodicity | default_start |
|---|---|---|---|---|
| 432 | Meta Selic (Copom) | % a.a. | diária (dias corridos) | 2012-06-01 |
| 433 | IPCA | % no mês | mensal (dia 1) | 2011-06-01 |

O IPCA começa 12 meses antes do período de análise para viabilizar o acumulado 12m em jun/2012.

## Bronze — captura bruta (Parquet, imutável)

Um arquivo por série por execução. Layout em [contracts/storage-layout.md](contracts/storage-layout.md).

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | string | campo `data` como veio da API (`dd/mm/aaaa`) |
| `valor` | string | campo `valor` como veio da API |
| `series_code` | int16 | código SGS |
| `window_start` | date | início da janela consultada |
| `window_end` | date | fim da janela consultada |
| `request_url` | string | URL completa da requisição |
| `extracted_at` | timestamp (UTC) | momento da resposta |
| `run_id` | string | identificador da execução (`YYYYMMDDTHHMMSSZ` + sufixo curto) |

Regras: nada é convertido; janela vazia gera zero linhas, não erro. Arquivos nunca são reescritos.

## Silver — `silver.sgs_series`

| Coluna | Tipo | Regra |
|---|---|---|
| `series_code` | smallint PK | |
| `name` | text not null | |
| `unit` | text not null | |
| `periodicity` | text not null | `daily` \| `monthly` |

Populada a partir do catálogo (upsert) a cada carga.

## Silver — `silver.sgs_observation`

| Coluna | Tipo | Regra |
|---|---|---|
| `series_code` | smallint not null, FK → `sgs_series` | |
| `ref_date` | date not null | parse de `data` (`dd/mm/aaaa`) |
| `value` | numeric(12,4) not null | parse de `valor`; não numérico → erro com `run_id` e arquivo |
| `source_run_id` | text not null | captura de origem |
| `source_extracted_at` | timestamptz not null | |
| `loaded_at` | timestamptz not null | muda só quando a linha muda |

- PK `(series_code, ref_date)`.
- Dedupe: para a mesma chave em várias capturas, vence a de maior `extracted_at`.
- Upsert: atualiza só se `value` ou `source_run_id` forem distintos (`IS DISTINCT FROM`).

## Gold — dbt (`dbt/models/`)

| Modelo | Materialização | Conteúdo |
|---|---|---|
| `stg_bcb_sgs__observations` | view | espelho de `silver.sgs_observation` com nomes padronizados |
| `int_selic_monthly` | view | por mês: média e valor do último dia disponível da série 432 |
| `int_ipca_monthly` | view | por mês: IPCA do mês e IPCA 12m composto (série 433) |
| `fct_monthly_macro_indicators` | table (schema `gold`) | junção dos dois por mês, de 2012-06 em diante |

### `fct_monthly_macro_indicators`

| Coluna | Tipo | Definição |
|---|---|---|
| `ref_month` | date | primeiro dia do mês (grão: 1 linha por mês) |
| `selic_target_avg` | numeric | média dos valores diários da série 432 no mês |
| `selic_target_eom` | numeric | valor da série 432 no último dia disponível do mês |
| `ipca_mom` | numeric | série 433 do mês |
| `ipca_12m` | numeric | `(exp(Σ ln(1 + ipca/100) dos 12 meses até o mês) − 1) × 100` |

- Linhas: de 2012-06 até o último mês com IPCA publicado (e com Selic no mês).
- Reconstruída a cada `dbt build`; resultado determinístico.

## Testes do dbt (FR-011)

| Teste | Tipo | Regra |
|---|---|---|
| `unique`, `not_null` em `ref_month` | genérico | grão de 1 linha por mês |
| `not_null` nos indicadores | genérico | nenhum indicador nulo |
| `accepted_range` | genérico próprio | Selic 1,5–30; IPCA mensal −2–5; IPCA 12m −5–20 |
| `assert_no_month_gaps` | singular | todos os meses entre o primeiro e o último presentes |
| `assert_starts_jun_2012` | singular | primeiro `ref_month` = 2012-06-01 |
| `assert_ipca_12m_official_values` | singular | dez/2015 10,67; dez/2017 2,95; dez/2021 10,06 (±0,01 p.p.) |

Cada teste retorna as linhas que violam a regra; zero linhas = passou.
