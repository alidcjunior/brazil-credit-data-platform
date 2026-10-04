---

description: "Task list for Fatia 1 — Selic e IPCA ponta a ponta"
---

# Tasks: Fatia 1 — Selic e IPCA ponta a ponta

**Input**: Design documents from `specs/001-selic-ipca-slice/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: MANDATORY (constitution, princípio IV). Testes unitários rodam sem rede e sem banco,
usando respostas reais gravadas da API. Testes de integração têm o marcador `db` e são pulados
automaticamente quando o Postgres não responde.

**Docker**: tarefas marcadas com 🐳 precisam do Postgres do `docker-compose.yml` (Docker ainda não
instalado). Todas as outras rodam agora. Ordem recomendada: tudo que não é 🐳 primeiro (ver
Implementation Strategy).

**Organization**: tarefas agrupadas por user story da spec (US1–US4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da spec (US1, US2, US3, US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: projeto Python com uv, ferramentas e arquivos de ambiente

- [ ] T001 Create `pyproject.toml` with uv (src layout, package `brcredit`, Python `>=3.13`, script entry `brcredit = "brcredit.cli:app"`), add runtime deps (httpx, tenacity, pyarrow, pandas, sqlalchemy>=2, psycopg[binary]>=3, typer, pydantic-settings, matplotlib, dbt-core, dbt-postgres) and dev deps (pytest, respx, ruff); generate `uv.lock`. If dbt-core has no release compatible with Python 3.13, pin the latest compatible one and record it in `specs/001-selic-ipca-slice/research.md` R6
- [ ] T002 [P] Configure ruff (line-length 100, rules E,F,I,B,UP) and pytest (`testpaths = ["tests"]`, marker `db: requires Postgres`) in `pyproject.toml`
- [ ] T003 [P] Create `.env.example` with `DATABASE_URL=postgresql+psycopg://brcredit:brcredit@localhost:5432/brcredit`, `DATA_DIR=./data`, `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5432`, `POSTGRES_USER=brcredit`, `POSTGRES_PASSWORD=brcredit`, `POSTGRES_DB=brcredit`; add `dbt/profiles.yml` to `.gitignore`
- [ ] T004 [P] Create `docker-compose.yml` with service `postgres` (`postgres:16-alpine`, env from `.env`, port 5432, named volume `pgdata`, healthcheck `pg_isready`)
- [ ] T005 [P] Create package skeleton: `src/brcredit/__init__.py`, `src/brcredit/sources/__init__.py`, `src/brcredit/bronze/__init__.py`, `src/brcredit/silver/__init__.py`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: config, catálogo de séries, esqueleto da CLI e infraestrutura de testes

**⚠️ CRITICAL**: nenhuma user story começa antes desta fase

- [ ] T006 Implement `Settings` (fields `database_url`, `data_dir: Path`, reading `.env`) in `src/brcredit/config.py` using pydantic-settings
- [ ] T007 [P] Implement series catalog in `src/brcredit/catalog.py`: frozen dataclass `Series(code, name, unit, periodicity, default_start)` with 432 (Meta Selic, `% a.a.`, `daily`, 2012-06-01) and 433 (IPCA, `% no mês`, `monthly`, 2011-06-01); `get_series(code)` raises `ValueError` listing valid codes
- [ ] T008 Create Typer app in `src/brcredit/cli.py` with sub-app `ingest` and logging to stderr; `uv run brcredit --help` must work
- [ ] T009 [P] Create `tests/conftest.py`: `fixtures_dir` fixture; auto-skip tests marked `db` when `DATABASE_URL` cannot connect (1 s timeout); `db_engine` fixture that recreates schemas `silver`, `gold*` for an isolated run
- [ ] T010 [P] Write `tests/unit/test_catalog.py` covering both series and the invalid-code error

**Checkpoint**: `uv run pytest` and `uv run ruff check .` pass; `uv run brcredit --help` works

---

## Phase 3: User Story 1 — Capturar o histórico bruto das séries (Priority: P1) 🎯 MVP

**Goal**: `brcredit ingest sgs` baixa 432 e 433 do período pedido, em janelas ≤ 10 anos, e grava
cada série como uma execução imutável em Parquet no bronze

**Independent Test**: com a API mockada (respx + fixtures reais), a captura cria
`data/bronze/bcb_sgs/serie=<c>/run=<run_id>/part-000.parquet` cobrindo todo o período, com colunas
brutas como string e metadados; uma segunda execução não altera a primeira

### Tests for User Story 1 (MANDATORY) ⚠️

- [ ] T011 [P] [US1] Record real API responses into `tests/fixtures/`: `sgs_432_2012-06-01_2012-07-31.json`, `sgs_433_2011-06-01_2012-12-01.json`, and the 406 body for a >10-year daily window as `sgs_432_406_window_too_large.json`; document URL and capture date in `tests/fixtures/README.md`
- [ ] T012 [P] [US1] Write `tests/unit/test_bcb_sgs_windows.py`: windows cover `[start, end]` with no gap/overlap, each ≤ 10 years minus 1 day, short period yields one window, `start > end` raises
- [ ] T013 [P] [US1] Write `tests/unit/test_bcb_sgs_client.py` (respx): URL uses `dd/mm/aaaa`; records returned unchanged as strings; empty list is valid; retries on timeout/503 then succeeds; does not retry on 406; raises after max attempts
- [ ] T014 [P] [US1] Write `tests/unit/test_bronze_writer.py` (tmp_path): run directory and Parquet columns match data-model (`data`, `valor` as string + metadata); second run leaves first untouched; failure mid-write leaves only `.tmp-run=*`, which readers ignore; `read_captures` returns rows from all runs
- [ ] T015 [P] [US1] Write `tests/unit/test_cli_ingest.py` (Typer CliRunner, client mocked): `--start > --end` and future `--end` fail before any request; unknown `--serie` fails listing valid codes; success prints one summary line per series and exits 0

### Implementation for User Story 1

- [ ] T016 [US1] Implement `split_windows(start, end, max_years=10)` in `src/brcredit/sources/bcb_sgs.py`
- [ ] T017 [US1] Implement SGS client in `src/brcredit/sources/bcb_sgs.py`: `fetch_window(code, start, end)` with httpx (timeout 30 s) + tenacity (4 attempts, exponential backoff 1/2/4 s, retry only timeout/connection/429/5xx) and `fetch_series(code, start, end)` iterating windows, yielding `(window, records, request_url, extracted_at)`
- [ ] T018 [US1] Implement `src/brcredit/bronze/writer.py`: `new_run_id()` (`YYYYMMDDTHHMMSSZ-<4hex>` UTC), `write_capture(data_dir, code, run_id, windows)` writing `serie=<c>/.tmp-run=<id>/part-000.parquet` then renaming to `run=<id>`, and `read_captures(data_dir, code)` reading all `run=*` directories
- [ ] T019 [US1] Implement `brcredit ingest sgs` in `src/brcredit/cli.py` per `contracts/cli.md` (`--serie` repeatable, `--start`, `--end`, validation, one shared `run_id`, summary line per series)
- [ ] T020 [US1] Run `uv run brcredit ingest sgs` against the real API and confirm both runs exist under `data/bronze/bcb_sgs/` covering 2012-06 (432) and 2011-06 (433) to today

**Checkpoint**: US1 complete and tested offline — first demonstrable increment, no Docker needed

---

## Phase 4: User Story 2 — Séries limpas e tipadas (Priority: P1)

**Goal**: `brcredit load-silver` transforma todas as capturas do bronze em `silver.sgs_observation`
tipada, uma linha por série + data, com upsert idempotente onde a captura mais recente vence

**Independent Test**: parse/dedupe testados sem banco; com Postgres, carregar duas vezes resulta
em zero linhas alteradas na segunda

### Tests for User Story 2 (MANDATORY) ⚠️

- [ ] T021 [P] [US2] Write `tests/unit/test_silver_parse.py`: `dd/mm/aaaa` → date; `"14.50"` → Decimal; non-numeric value raises error naming `run_id`; for duplicate `(series_code, ref_date)` the row with greatest `extracted_at` wins
- [ ] T022 [P] [US2] 🐳 Write `tests/integration/test_silver_loader.py` (marker `db`): `init-db` runs twice without error; first load inserts all rows; second load reports 0 inserted/0 updated and leaves table identical including `loaded_at`; a newer capture with a different value updates only that row

### Implementation for User Story 2

- [ ] T023 [US2] Implement pure `parse_captures(df) -> DataFrame` and `dedupe_latest(df)` in `src/brcredit/silver/loader.py`
- [ ] T024 [P] [US2] Write DDL in `src/brcredit/silver/schema.sql` per data-model (`silver.sgs_series`, `silver.sgs_observation` with PK and FK, `CREATE ... IF NOT EXISTS`)
- [ ] T025 [US2] Implement `src/brcredit/db.py`: `get_engine(settings)` and `init_db(engine)` applying `silver/schema.sql` (package resource)
- [ ] T026 [US2] Implement `load_silver(engine, data_dir)` in `src/brcredit/silver/loader.py`: upsert catalog into `sgs_series`; upsert observations via `INSERT ... ON CONFLICT (series_code, ref_date) DO UPDATE ... WHERE value IS DISTINCT FROM excluded.value OR source_run_id IS DISTINCT FROM excluded.source_run_id`; return counts inserted/updated/unchanged
- [ ] T027 [US2] Add `init-db` and `load-silver` commands to `src/brcredit/cli.py` printing the counts
- [ ] T028 [US2] 🐳 `docker compose up -d --wait`, run `init-db` + `load-silver` twice on real bronze data and confirm second run reports 0 changes

**Checkpoint**: US1 + US2 entregam ingestão completa até silver

---

## Phase 5: User Story 3 — Visão mensal Selic x IPCA em dbt (Priority: P2)

**Goal**: `brcredit build-gold` executa `dbt build` e produz `gold.fct_monthly_macro_indicators`
com Selic média/fim de mês e IPCA mensal/12m, validada pelos testes do dbt

**Independent Test**: o projeto dbt compila sem banco (`dbt parse`); com Postgres, dados sintéticos
de silver geram os valores calculados à mão, e com dados reais todos os testes do dbt passam

### Tests for User Story 3 (MANDATORY) ⚠️

- [ ] T029 [P] [US3] Write `tests/unit/test_dbt_project.py`: `dbtRunner().invoke(["parse", ...])` on `dbt/` succeeds using `dbt/profiles.yml.example` values (no DB connection needed)
- [ ] T030 [P] [US3] 🐳 Write `tests/integration/test_build_gold.py` (marker `db`): insert synthetic silver rows for 14 months, run `dbt run`, assert one row per month, `selic_target_avg`/`selic_target_eom` and `ipca_12m` equal hand-computed values; running twice gives identical table

### Implementation for User Story 3

- [ ] T031 [US3] Create `dbt/dbt_project.yml` (profile `brcredit`; `staging` and `intermediate` as views with `+schema: staging`/`intermediate`; `marts` as table in default schema) and `dbt/profiles.yml.example` (target schema `gold`, connection from `env_var('POSTGRES_*')`)
- [ ] T032 [P] [US3] Create `dbt/models/staging/_sources.yml` (source `silver.sgs_observation`) and `dbt/models/staging/stg_bcb_sgs__observations.sql` (`series_code`, `ref_date`, `value`)
- [ ] T033 [P] [US3] Create `dbt/models/intermediate/int_selic_monthly.sql`: per month for series 432, `selic_target_avg` (avg) and `selic_target_eom` (value on max date of month)
- [ ] T034 [P] [US3] Create `dbt/models/intermediate/int_ipca_monthly.sql`: per month for series 433, `ipca_mom` and `ipca_12m = (exp(sum(ln(1 + ipca_mom/100)) over 12 rows) - 1) * 100`, null when the window has fewer than 12 months
- [ ] T035 [US3] Create `dbt/models/marts/fct_monthly_macro_indicators.sql` (inner join by month, `ref_month >= '2012-06-01'`) and `dbt/models/marts/_marts.yml` with column descriptions, `unique`/`not_null` tests and `accepted_range` per data-model
- [ ] T036 [P] [US3] Create generic test `dbt/tests/generic/accepted_range.sql` (args `min_value`, `max_value`)
- [ ] T037 [P] [US3] Create singular tests `dbt/tests/assert_no_month_gaps.sql`, `dbt/tests/assert_starts_jun_2012.sql`, `dbt/tests/assert_ipca_12m_official_values.sql` (dez/2015 10.67, dez/2017 2.95, dez/2021 10.06, tolerance 0.01)
- [ ] T038 [US3] Add `build-gold` command to `src/brcredit/cli.py` invoking `dbtRunner` `build` with `--project-dir dbt --profiles-dir dbt`, loading `.env` first; exit ≠ 0 when any model or test fails
- [ ] T039 [US3] 🐳 Run `uv run brcredit build-gold` on real silver data and confirm all dbt tests pass

**Checkpoint**: resposta analítica da fatia disponível em `gold.fct_monthly_macro_indicators`

---

## Phase 6: User Story 4 — Gráfico Selic x IPCA (Priority: P3)

**Goal**: `brcredit chart` gera um PNG com Selic meta e IPCA 12m por mês, com título, legenda,
unidades e fonte

**Independent Test**: a função de gráfico, alimentada com um DataFrame conhecido, gera um PNG não
vazio com os textos esperados

### Tests for User Story 4 (MANDATORY) ⚠️

- [ ] T040 [P] [US4] Write `tests/unit/test_chart.py`: `render_chart(df, output)` creates a non-empty PNG; returned figure has title, legend labels "Meta Selic (% a.a.)" and "IPCA 12 meses (%)", and source note "Fonte: BCB/SGS (séries 432 e 433)"

### Implementation for User Story 4

- [ ] T041 [US4] Implement `src/brcredit/chart.py`: `read_gold(engine) -> DataFrame` and `render_chart(df, output)` (matplotlib `Agg`, both series on the same time axis, labeled axes, source note)
- [ ] T042 [US4] Add `chart` command (`--output`, default `docs/img/selic_vs_ipca.png`) to `src/brcredit/cli.py`
- [ ] T043 [US4] 🐳 Generate `docs/img/selic_vs_ipca.png` from real gold data and check it visually

**Checkpoint**: todas as user stories funcionando

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T044 Add `run` command to `src/brcredit/cli.py` (`ingest sgs` → `init-db` → `load-silver` → `build-gold` → `chart`, stops on first failure) with `tests/unit/test_cli_run.py` asserting step order and early stop (steps mocked)
- [ ] T045 [P] Write `docs/adr/0001-parquet-no-bronze.md` (context, decision: Parquet imutável por execução no bronze; alternatives: JSON cru, sobrescrever partição; consequences)
- [ ] T046 [P] Write `docs/architecture.md` with Mermaid diagram (API SGS → bronze Parquet → silver Postgres → dbt staging/intermediate/marts → gráfico) and the role of each layer
- [ ] T047 Update `README.md`: como rodar (quickstart resumido), o que a Fatia 1 entrega, gráfico embutido, atribuição da fonte BCB, roadmap com Fatia 1 marcada e item "Airflow + dbt" renomeado para "Airflow" (dbt antecipado)
- [ ] T048 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` (unit; integration too when 🐳 available); fix findings in files touched by this feature
- [ ] T049 🐳 Validate `quickstart.md` from a clean clone: time to chart ≤ 15 min (SC-001), full `brcredit run` ≤ 5 min (SC-002), second `run` reports 0 silver changes (SC-005), unit tests < 1 min offline (SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories
- **US1** depende só da Foundational
- **US2** depende de US1 (lê o bronze); T021/T023/T024 podem começar junto com US1
- **US3** depende de US2 (lê o silver); T029/T031–T037 (arquivos dbt) não precisam de banco e podem
  começar cedo
- **US4** depende de US3 (lê o gold); T040/T041 `render_chart` podem começar cedo
- **Polish** depende de todas as stories

### Within Each User Story

- Testes escritos junto com o código que cobrem (princípio IV) e rodando antes do checkpoint
- Funções puras antes de I/O (janelas → cliente; parse/dedupe → upsert)
- Tarefas 🐳 por último dentro de cada story

### Parallel Opportunities

- Setup: T002, T003, T004, T005
- Foundational: T007, T009, T010
- US1 tests: T011–T015 juntos
- US3 dbt files: T032, T033, T034, T036, T037 juntos

## Parallel Example: User Story 1

```bash
Task: "Record real API responses into tests/fixtures/"
Task: "Write tests/unit/test_bcb_sgs_windows.py"
Task: "Write tests/unit/test_bronze_writer.py"
Task: "Write tests/unit/test_cli_ingest.py"
```

---

## Implementation Strategy

### Agora (sem Docker)

1. Phase 1 + Phase 2
2. US1 completa (T011–T020) → **MVP: captura real no bronze, testada offline**
3. Partes offline de US2–US4: T021, T023, T024, T025, T026, T027 (código + teste puro),
   T029, T031–T038 (dbt compila com `dbt parse`), T040–T042, T044, T045, T046

### Depois do Docker

4. Tarefas 🐳: T022, T028, T030, T039, T043
5. T047, T048, T049 → fatia concluída (constitution: só fecha depois de rodar com Docker)

### Notes

- [P] = arquivos diferentes, sem dependência pendente
- Commit após cada task ou grupo lógico (o autor faz o push)
- Arquivos fora desta lista não são alterados; problemas fora do escopo são reportados
