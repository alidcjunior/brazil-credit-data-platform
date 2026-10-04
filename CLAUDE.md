<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
specs/001-selic-ipca-slice/plan.md
<!-- SPECKIT END -->

# Brazil Credit & Economy Data Platform

Projeto de portfólio pessoal (público no GitHub). Plataforma de dados
ponta a ponta com dados públicos brasileiros. Projeto 1 de 3 do portfólio
(2: processamento em escala com PySpark sobre CNPJ da Receita;
3: reclamações de consumidores + classificação com LLM).

Todo o código é escrito do zero. Não reutilizar código, nomes, regras de
negócio ou dados de nenhum empregador.

## Pergunta de negócio

Como juros (Selic) e inflação (IPCA) se relacionam com o volume de crédito
e a inadimplência em cada estado brasileiro ao longo do tempo?

## Fontes (validadas em 2026-10-04)

- BCB SGS (API REST, JSON):
  `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`
  Séries candidatas: 432 (meta Selic), 433 (IPCA mensal), 1 (dólar PTAX venda).
  Séries diárias têm limite de janela por requisição: paginar por período.
- BCB SCR.data (dados abertos, mensal, por UF, desde jun/2012, licença ODbL):
  `https://dadosabertos.bcb.gov.br/dataset/scr_data`
  Carteira ativa, inadimplência e ativo problemático por UF, modalidade,
  porte e tipo de cliente (PF/PJ). Publicado cerca de 30 dias após o
  fechamento do mês.
- IBGE SIDRA (API REST): população e PIB por UF, pra métricas per capita.

## Arquitetura pretendida

Bronze (raw em Parquet, imutável) → silver (PostgreSQL, limpo e tipado)
→ gold (modelos dbt, dimensional). Orquestração com Airflow, tudo em
Docker Compose, CI com GitHub Actions, dashboard em Metabase ou Streamlit.

## Princípios de trabalho

- Spec antes de código: toda feature começa com /speckit-specify.
- Entrega em fatias verticais: uma fonte ponta a ponta (ingestão → bronze
  → silver → gold → gráfico, com testes) antes de adicionar outras.
- Cargas incrementais com janela de repescagem (fontes do BCB revisam
  dados retroativamente) e reprocessamento idempotente.
- Testes desde a primeira fatia, não no final.
- Documentação (README, decisões de arquitetura) é parte da entrega.
