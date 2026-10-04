# Implementation Plan: Fatia 1 — Selic e IPCA ponta a ponta

**Branch**: `001-selic-ipca-slice` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-selic-ipca-slice/spec.md`

## Summary

Capturar as séries SGS 432 (meta Selic) e 433 (IPCA) da API do BCB, paginando em janelas de até
10 anos, guardar cada resposta sem conversão em Parquet imutável (bronze), carregar em PostgreSQL
com upsert idempotente por série + data (silver), modelar em dbt uma visão mensal com Selic média
e de fim de mês e IPCA mensal e 12m (gold), validada por testes do dbt, e gerar um gráfico PNG.
Tudo exposto pela CLI `brcredit`. Como o Docker ainda não está instalado, a implementação começa
pela parte sem banco (fonte, janelas, bronze, parsing — tudo testado offline) e termina com
silver/dbt/gráfico quando o Postgres do `docker-compose.yml` estiver disponível.

## Technical Context

**Language/Version**: Python 3.13; SQL (PostgreSQL) nos modelos dbt
**Primary Dependencies**: httpx, tenacity, pyarrow, pandas, SQLAlchemy 2 + psycopg 3, typer,
pydantic-settings, matplotlib, dbt-core + dbt-postgres; dev: pytest, respx, ruff
**Storage**: bronze em Parquet no disco local (`data/`); silver e gold em PostgreSQL 16 (Docker Compose)
**Testing**: pytest — `tests/unit` offline (fixtures reais gravadas + respx); `tests/integration`
com marcador `db`, pulados automaticamente sem banco; testes de dados do dbt no gold
**Target Platform**: Windows 11 local (dev); Linux em containers/CI nas próximas fatias
**Project Type**: pipeline de dados com CLI (projeto Python único, layout `src/`) + projeto dbt
**Performance Goals**: fluxo completo jun/2012→hoje em ≤ 5 min (SC-002); testes offline < 1 min (SC-006)
**Constraints**: janela máxima de 10 anos por requisição na série diária; sem autenticação;
bronze nunca reescrito; carga idempotente
**Scale/Scope**: ~5,2 mil observações diárias (432) + ~185 mensais (433); ~172 meses no gold

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Como o plano atende |
|---|---|---|
| I. Spec antes de código | ✅ | spec.md → este plan → tasks.md antes de qualquer código |
| II. Fatias verticais | ✅ | uma fonte (SGS) ponta a ponta até gráfico; incremental, CI, Airflow fora |
| III. Incremental e idempotente | ✅ (parcial por escopo) | bronze imutável por `run_id`; upsert `IS DISTINCT FROM`; gold reconstruído pelo dbt; reprocesso por `--start/--end`. Janela de repescagem é a próxima fatia |
| IV. Testes desde a primeira fatia | ✅ | unit offline com fixtures reais; teste de idempotência; testes do dbt no gold, inclusive IPCA 12m oficial |
| V. Reprodutibilidade com Docker | ⚠️ justificado | `docker-compose.yml` e `uv.lock` entram nesta fatia; tasks com banco ficam por último e a fatia só fecha depois de rodar com Docker (ver Complexity Tracking) |
| VI. Código original, dados públicos | ✅ | código novo; SGS é dado público; atribuição de fonte no README e no gráfico |
| VII. Documentação | ✅ | README, `docs/architecture.md`, ADR-0001, gráfico em `docs/img/` |

**Re-check pós-design**: sem novas violações. Antecipar o dbt para esta fatia não fere a ordem da
constitution: é o destino declarado do gold, e Airflow continua na fatia própria.

## Project Structure

### Documentation (this feature)

```text
specs/001-selic-ipca-slice/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   └── storage-layout.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

Segue a estrutura-alvo do autor; só é criado o que esta fatia usa.

```text
src/brcredit/
├── __init__.py
├── config.py              # Settings (DATABASE_URL, DATA_DIR) via pydantic-settings + .env
├── catalog.py             # séries 432/433: nome, unidade, periodicidade, início padrão
├── sources/
│   ├── __init__.py
│   └── bcb_sgs.py         # janelas ≤ 10 anos + cliente httpx/tenacity; só fala com a API
├── bronze/
│   ├── __init__.py
│   └── writer.py          # escrita atômica por run_id e leitura das capturas
├── silver/
│   ├── __init__.py
│   ├── schema.sql         # DDL silver (CREATE ... IF NOT EXISTS)
│   └── loader.py          # parse/dedupe (puro) + upsert no Postgres
├── db.py                  # engine SQLAlchemy, init-db
├── chart.py               # PNG Selic x IPCA 12m (matplotlib, backend Agg)
└── cli.py                 # typer: ingest sgs, init-db, load-silver, build-gold, chart, run

dbt/
├── dbt_project.yml
├── profiles.yml.example   # lê conexão de env vars; copiar para dbt/profiles.yml (gitignored)
├── models/
│   ├── staging/           # _sources.yml, stg_bcb_sgs__observations.sql
│   ├── intermediate/      # int_selic_monthly.sql, int_ipca_monthly.sql
│   └── marts/             # fct_monthly_macro_indicators.sql + _marts.yml (testes)
└── tests/
    ├── generic/           # accepted_range.sql
    └── *.sql              # assert_no_month_gaps, assert_starts_jun_2012, assert_ipca_12m_official_values

tests/
├── conftest.py            # skip automático de `db` sem banco
├── fixtures/              # respostas reais da API SGS em JSON
├── unit/                  # janelas, cliente, bronze, parse/dedupe, chart
└── integration/           # upsert, idempotência, build-gold (dbt) ponta a ponta

docs/
├── architecture.md        # diagrama e fluxo de dados
├── adr/0001-parquet-no-bronze.md
└── img/selic_vs_ipca.png

data/                      # bronze local (gitignored)
docker-compose.yml         # postgres:16-alpine + healthcheck + volume
pyproject.toml             # deps, entry point `brcredit`, config ruff/pytest
uv.lock
.env.example
```

Fica para as fatias próprias (não criado agora): `sources/bcb_scr.py`, `sources/ibge_sidra.py`,
`incremental/state.py`, `.github/workflows/ci.yml`, `airflow/`, `dashboard/`, `Dockerfile`.

**Structure Decision**: projeto Python único com layout `src/` e pacote `brcredit`, mais projeto
dbt em `dbt/` para o gold. O gráfico fica em `src/brcredit/chart.py` até existir `dashboard/`.
Parse/dedupe do silver é função pura separada do upsert, para ser testada sem banco.

## Ordem de implementação (decisão do autor: Docker depois)

1. **Sem banco** (roda agora): setup (uv, ruff, pytest), catálogo, janelas e cliente SGS com
   retry, gravação de fixtures reais, bronze, parse/dedupe do silver, `brcredit ingest sgs`,
   testes unitários; esqueleto do projeto dbt (`dbt parse` roda sem banco).
2. **Com banco** (após instalar Docker): compose em uso, `init-db`, upsert silver, modelos e
   testes dbt, gráfico, `brcredit run`, testes de integração (idempotência, build-gold).
3. **Fechamento**: README, `docs/architecture.md`, ADR-0001, gráfico versionado, quickstart do zero.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Princípio V parcialmente adiado: Docker Compose escrito mas não executado até a fase 2 | Docker Desktop ainda não instalado; autor optou por não bloquear o início (2026-10-04) | Postgres nativo no Windows: diverge do ambiente reprodutível e vira retrabalho; DuckDB temporário: muda a arquitetura do silver |
