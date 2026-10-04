# Brazil Credit & Economy Data Platform

> 🚧 Em construção

Plataforma de dados ponta a ponta construída com dados públicos brasileiros
para responder:

**Como juros e inflação se relacionam com o volume de crédito e a
inadimplência em cada estado brasileiro ao longo do tempo?**

## Fontes de dados

| Fonte | Conteúdo | Frequência |
|---|---|---|
| [Banco Central — SGS](https://www3.bcb.gov.br/sgspub/) | Selic, IPCA, câmbio | Diária / mensal |
| [Banco Central — SCR.data](https://dadosabertos.bcb.gov.br/dataset/scr_data) | Carteira de crédito e inadimplência por UF | Mensal |
| [IBGE — SIDRA](https://sidra.ibge.gov.br/) | População e PIB por UF | Anual |

## Arquitetura (planejada)

```
APIs públicas ──► Bronze (Parquet) ──► Silver (PostgreSQL) ──► Gold (dbt) ──► Dashboard
                         └──────────── orquestrado por Airflow ────────────┘
```

## Stack

Python · PostgreSQL · Parquet · dbt · Airflow · Docker Compose · GitHub Actions · pytest

## Roadmap

- [ ] Fatia 1: Selic e IPCA ponta a ponta (ingestão → bronze → silver → gold → gráfico)
- [ ] Carga incremental com janela de repescagem e idempotência
- [ ] CI com GitHub Actions
- [ ] Orquestração com Airflow e modelagem com dbt
- [ ] SCR.data (crédito e inadimplência por UF)
- [ ] IBGE (métricas per capita)
- [ ] Dashboard e documentação de decisões de arquitetura
