# Contract: layout de armazenamento

## Bronze (sistema de arquivos, raiz `DATA_DIR`, padrão `./data`)

```text
data/bronze/bcb_sgs/
└── serie=<codigo>/
    └── run=<run_id>/            # uma execução de captura; nunca reescrita
        ├── part-000.parquet     # todas as janelas da série nesta execução
        └── manifest.parquet     # uma linha por janela consultada (inclusive vazias)
```

- `run_id` = `YYYYMMDDTHHMMSSZ-<4 hex>` (UTC), compartilhado por todas as séries da mesma execução.
- Escrita: `serie=<c>/.tmp-run=<run_id>/` → rename para `run=<run_id>/` ao fim. Diretórios
  `.tmp-*` são ignorados pela leitura (sobra de execução que falhou).
- Leitura (silver): todos os `run=*/part-*.parquet` de cada série.
- `data/` está no `.gitignore`.

## Banco (PostgreSQL 16)

| Schema | Objetos | Dono |
|---|---|---|
| `silver` | `sgs_series`, `sgs_observation` | `brcredit load-silver` (DDL em `src/brcredit/silver/schema.sql`, aplicado por `init-db`) |
| `gold_staging`, `gold_intermediate` | views do dbt | `brcredit build-gold` |
| `gold` | `fct_monthly_macro_indicators` | `brcredit build-gold` |

## Conexão

- Python: `DATABASE_URL=postgresql+psycopg://brcredit:brcredit@localhost:5432/brcredit`
  (valor de `.env.example`, coincide com o `docker-compose.yml`).
- Testes de integração: `TEST_DATABASE_URL=postgresql+psycopg://brcredit:brcredit@localhost:5432/brcredit_test`
  (banco criado pelo script de init do compose; a fixture recusa banco cujo nome não termine em `_test`).
- dbt: `dbt/profiles.yml.example` lê `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`,
  `POSTGRES_PASSWORD`, `POSTGRES_DB` via `env_var()`; também definidos no `.env.example`.
