# Research: Fatia 1 — Selic e IPCA ponta a ponta

Decisões técnicas da fatia. Nenhum item ficou como NEEDS CLARIFICATION.

## R1. Contrato da API SGS (validado em 2026-10-04)

- **Decision**: consumir `GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`.
- Fatos observados:
  - Resposta: lista JSON `[{"data": "dd/mm/aaaa", "valor": "14.50"}, ...]`; valores são **strings**
    com ponto decimal.
  - Série 432 (meta Selic, % a.a.) tem **um valor por dia corrido**, inclusive fins de semana.
  - Série 433 (IPCA, % no mês) tem um valor por mês, datado no dia 1.
  - Janela > 10 anos em série diária → **HTTP 406** com JSON `{"error": "...no máximo, 10 anos..."}`.
- **Rationale**: é a fonte oficial e não exige autenticação.
- **Alternatives**: biblioteca `python-bcb` (rejeitada: esconde exatamente a paginação e o formato
  bruto que o projeto quer demonstrar).

## R2. Paginação por janela

- **Decision**: dividir `[start, end]` em janelas consecutivas de no máximo 10 anos menos 1 dia
  (`[a, b]`, próxima começa em `b + 1 dia`), aplicada a **todas** as séries (inclusive mensais),
  por simplicidade e uniformidade.
- **Rationale**: elimina buracos e sobreposição por construção; testável como função pura.
- **Alternatives**: janela por série/periodicidade (mais regras sem ganho real; o volume é pequeno).

## R3. Cliente HTTP e retry

- **Decision**: `httpx` (timeout 30 s) + `tenacity`: até 4 tentativas com backoff exponencial
  (1 s, 2 s, 4 s) apenas para timeout, erro de conexão e HTTP 429/5xx. HTTP 4xx (ex.: 406) não é
  repetido: é erro de requisição.
- **Rationale**: a API do BCB tem instabilidade ocasional; 4xx indica bug nosso.
- **Alternatives**: `requests` + `urllib3.Retry` (funciona, mas `httpx` + `respx` torna os testes
  offline mais simples).

## R4. Bronze: formato e imutabilidade

- **Decision**: Parquet via `pyarrow`, **um diretório por execução de captura** (`run_id`),
  gravado primeiro em diretório temporário e renomeado só quando todas as janelas da série
  terminam (captura parcial nunca fica visível). Colunas brutas `data` e `valor` como **string**,
  sem conversão, mais metadados (série, janela, URL, timestamp, `run_id`).
- **Rationale**: atende FR-003 (cópia fiel e imutável) e o edge case de falha no meio da captura.
- **Alternatives**: guardar o JSON cru em arquivo `.json` (mais fiel, mas perde o formato colunar
  que a arquitetura define para o bronze); sobrescrever por partição de data (viola imutabilidade).

## R5. Silver: upsert idempotente

- **Decision**: PostgreSQL 16, tabela `silver.sgs_observation` com PK `(series_code, ref_date)`.
  A carga lê **todas** as capturas do bronze, deduplica mantendo a de `extracted_at` mais recente
  e faz `INSERT ... ON CONFLICT DO UPDATE ... WHERE` valor ou captura de origem mudaram
  (`IS DISTINCT FROM`). `loaded_at` só muda quando a linha muda de fato.
- **Rationale**: rodar duas vezes não altera nada (FR-006, SC-005); captura mais recente vence
  (FR-007).
- **Alternatives**: truncate + insert (idempotente, mas perde a auditoria de quando cada valor
  mudou e não escala para o incremental da próxima fatia).

## R6. Gold em dbt desde a Fatia 1

- **Decision**: gold modelado em `dbt/` com `dbt-core` + `dbt-postgres` (instalados via `uv` no
  mesmo ambiente). Camadas: `staging` (views, `stg_bcb_sgs__observations` espelha o silver),
  `intermediate` (views: `int_selic_monthly`, `int_ipca_monthly`), `marts` (tabela
  `fct_monthly_macro_indicators`, schema `gold`). IPCA 12m composto:
  `(exp(sum(ln(1 + ipca/100)) over 12 meses) - 1) * 100`, só quando há 12 meses na janela.
  A CLI chama o dbt programaticamente (`dbtRunner`) em `brcredit build-gold`.
- **Rationale**: decisão do autor (2026-10-04): o gold nasce no destino final, sem migração
  depois; a fatia futura "Airflow + dbt" passa a ser só Airflow. dbt roda contra o Postgres do
  compose, sem container extra.
- **Alternatives**: SQL puro em `sql/` e migração para dbt depois (rejeitada: reescreve gold e
  checks).
- **Verificar no setup**: compatibilidade da versão do dbt-core com Python 3.13 no momento do
  `uv add`; se não houver, fixar a versão mais recente compatível.

## R7. Verificações de dados (FR-011) como testes do dbt

- **Decision**: testes do dbt executados no `dbt build`:
  - genéricos: `unique` e `not_null` em `ref_month` e indicadores;
  - genérico próprio `accepted_range` em `dbt/tests/generic/` (sem pacote externo): Selic meta
    1,5–30 % a.a.; IPCA mensal −2–5 %; IPCA 12m −5–20 %;
  - singulares em `dbt/tests/`: `assert_no_month_gaps`, `assert_starts_jun_2012`,
    `assert_ipca_12m_official_values` (dez/2015 = 10,67 %; dez/2017 = 2,95 %; dez/2021 = 10,06 %,
    tolerância 0,01 p.p. — SC-004).
- **Rationale**: é o padrão do dbt; falha no teste falha o `build-gold` (saída ≠ 0).
- **Alternatives**: `dbt-utils`/`dbt-expectations` (dependência a mais para 1 teste simples).

## R8. Testes offline vs. com banco

- **Decision**:
  - `tests/unit/` — sem rede e sem banco: janelas, cliente (com `respx` servindo fixtures reais
    gravadas em `tests/fixtures/sgs/`), retry, escrita/leitura do bronze, parsing/deduplicação.
  - `tests/integration/` — marcador `db`; precisam de Postgres em `DATABASE_URL`; são
    **pulados automaticamente** se o banco não responde. Cobrem upsert, idempotência e
    `build-gold` ponta a ponta (dbt build com testes).
- **Rationale**: o Docker ainda não está instalado; a parte offline já é testável e roda no CI
  futuro sem serviços.
- **Alternatives**: `testcontainers` (exige Docker do mesmo jeito); SQLite como substituto
  (comportamento de upsert/tipos diferente do Postgres).

## R9. CLI, config e ferramentas

- **Decision**: CLI `brcredit` com `typer` (pacote `brcredit`); config por variáveis de ambiente lidas com
  `pydantic-settings` (`.env` local, `.env.example` versionado); `uv` com `uv.lock`; `ruff` para
  lint e format; gráfico com `matplotlib` (backend `Agg`, sem janela).
- **Rationale**: stack enxuta, toda instalável por `uv sync`, funciona no Windows.

## R10. Docker Compose sem Docker instalado

- **Decision**: `docker-compose.yml` (Postgres 16-alpine, healthcheck, volume nomeado) entra no
  repositório nesta fatia, mas as tasks que dependem dele ficam no fim da ordem de implementação.
  A fatia só é concluída depois de rodar com o Docker (constitution, princípio V).
- **Rationale**: decisão do autor em 2026-10-04: não bloquear o início pela instalação do Docker.
