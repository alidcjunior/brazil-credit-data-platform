# Quickstart: Fatia 1 — Selic e IPCA

Pré-requisitos: Python 3.13, [uv](https://docs.astral.sh/uv/), Docker Desktop (para as etapas com
banco). Comandos para PowerShell ou Git Bash, a partir da raiz do repositório.

## 1. Instalar dependências

```bash
uv sync
cp .env.example .env
cp dbt/profiles.yml.example dbt/profiles.yml
```

## 2. Testes offline (não precisam de Docker nem internet)

```bash
uv run pytest tests/unit
uv run ruff check .
```

## 3. Captura (bronze) — precisa só de internet

```bash
uv run brcredit ingest sgs
```

Esperado: uma execução em `data/bronze/bcb_sgs/serie=432/` e outra em `serie=433/`.

## 4. Banco, silver, gold e gráfico — precisa de Docker

```bash
docker compose up -d --wait
uv run brcredit init-db
uv run brcredit load-silver
uv run brcredit build-gold      # dbt build: modelos + testes
uv run brcredit chart
```

Esperado: `build-gold` com todos os testes do dbt passando e `docs/img/selic_vs_ipca.png` gerado.
Atalho para tudo: `uv run brcredit run`.

## 5. Testes com banco

```bash
uv run pytest            # unit + integration (integration é pulado se o banco não responder)
```

## Validação da fatia

- Rodar `uv run brcredit run` duas vezes: o segundo `load-silver` informa 0 linhas alteradas.
- O teste `assert_ipca_12m_official_values` confere dez/2015, dez/2017 e dez/2021 contra os
  valores oficiais (10,67 %, 2,95 %, 10,06 %).
