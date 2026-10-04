# Contract: CLI `brcredit`

Executada com `uv run brcredit <comando>`. Código de saída 0 = sucesso; ≠ 0 = falha, com mensagem
em stderr. Logs em stderr; resumo final em stdout.

| Comando | Opções | Efeito | Precisa de banco |
|---|---|---|---|
| `ingest sgs` | `--serie 432 --serie 433` (padrão: todas do catálogo); `--start AAAA-MM-DD` (padrão: início de cada série); `--end AAAA-MM-DD` (padrão: hoje) | captura janelas da API e grava uma execução no bronze | não |
| `init-db` | — | cria schemas e tabelas do silver (idempotente) | sim |
| `load-silver` | — | lê todas as capturas do bronze e faz upsert em `silver` | sim |
| `build-gold` | — | `dbt build` no projeto `dbt/` (modelos + testes); sai ≠ 0 se algum teste falhar | sim |
| `chart` | `--output CAMINHO` (padrão: `docs/img/selic_vs_ipca.png`) | gera o PNG a partir de `gold.fct_monthly_macro_indicators` | sim |
| `run` | mesmas de `ingest sgs` | `ingest sgs` → `init-db` → `load-silver` → `build-gold` → `chart` | sim |

## Regras de validação

- `--start` > `--end` ou `--end` no futuro → erro antes de qualquer requisição.
- Série fora do catálogo → erro listando as séries válidas.
- Falha de rede persistente após retries → saída ≠ 0, nenhuma execução parcial visível no bronze.

## Exemplo de saída (`ingest sgs`)

```text
432  2012-06-01 → 2026-10-04  2 janelas  5239 linhas  data/bronze/bcb_sgs/serie=432/run=20261004T183000Z-a1b2/
433  2011-06-01 → 2026-10-04  2 janelas   184 linhas  data/bronze/bcb_sgs/serie=433/run=20261004T183000Z-a1b2/
```
