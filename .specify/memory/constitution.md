<!--
Sync Impact Report
- Versão: (template sem versão) → 1.0.0 (ratificação inicial)
- Princípios definidos:
  I. Spec Antes de Código
  II. Fatias Verticais
  III. Cargas Incrementais e Idempotentes
  IV. Testes Desde a Primeira Fatia (NÃO NEGOCIÁVEL)
  V. Reprodutibilidade com Docker
  VI. Código Original e Dados Públicos
  VII. Documentação Faz Parte da Entrega
- Seções adicionadas: Restrições Técnicas; Fluxo de Trabalho
- Seções removidas: nenhuma
- Templates:
  ✅ .specify/templates/tasks-template.md (testes deixam de ser opcionais)
  ✅ .specify/templates/plan-template.md (Constitution Check lê este arquivo; sem mudança)
  ✅ .specify/templates/spec-template.md (sem mudança necessária)
  ✅ README.md (já coerente com os princípios)
  ⚠ .specify/templates/commands/ não existe neste projeto; nada a verificar
- TODOs: nenhum
-->

# Brazil Credit & Economy Data Platform Constitution

## Core Principles

### I. Spec Antes de Código

Toda feature MUST começar com `/speckit-specify` e seguir o fluxo spec → plan → tasks →
implement. Código só é escrito para cumprir uma task do `tasks.md` da spec ativa.
Exceção: leituras rápidas (ler arquivo, grep, uma chamada exploratória de API) não
precisam de spec.

**Razão**: o projeto é portfólio; o rastro spec → código demonstra o processo, não só o
resultado.

### II. Fatias Verticais

Cada fonte de dados MUST ser entregue ponta a ponta (ingestão → bronze → silver → gold →
visualização, com testes) antes de outra fonte começar. Uma fatia só está pronta quando
roda do zero em ambiente limpo e produz um resultado visível. Ordem planejada: Selic+IPCA
→ incremental e idempotência → CI → Airflow+dbt → SCR.data → IBGE → dashboard e docs.

**Razão**: cada fatia entrega valor demonstrável e expõe problemas de integração cedo.

### III. Cargas Incrementais e Idempotentes

- Bronze MUST ser imutável: cada extração grava um novo arquivo Parquet com a resposta
  bruta da fonte e metadados de extração (fonte, parâmetros, timestamp); nada é sobrescrito.
- Toda carga MUST ser idempotente: reexecutar com os mesmos parâmetros produz o mesmo estado
  em silver e gold, sem duplicar linhas (upsert por chave natural).
- Cargas incrementais MUST reprocessar uma janela de repescagem configurável, porque o BCB
  revisa dados retroativamente.
- Reprocessar qualquer período histórico MUST ser possível sem intervenção manual.

**Razão**: fontes públicas revisam dados; o pipeline tem que convergir para a versão
correta sem retrabalho.

### IV. Testes Desde a Primeira Fatia (NÃO NEGOCIÁVEL)

- Todo código de ingestão, transformação e carga MUST ter testes automatizados entregues na
  mesma task ou fatia, nunca deixados para o final.
- Testes unitários MUST rodar sem rede, usando fixtures com respostas reais gravadas das
  fontes.
- Toda carga MUST ter um teste de idempotência (rodar duas vezes e comparar o estado).
- Modelos gold MUST ter testes de dados (unicidade, não nulo, faixas plausíveis).
- Ferramentas: pytest para Python; testes do dbt quando o dbt entrar.

**Razão**: pipelines de dados quebram em silêncio; testes são a única garantia de que um
número no dashboard está certo.

### V. Reprodutibilidade com Docker

Todos os serviços (PostgreSQL, Airflow, dashboard) MUST subir com Docker Compose a partir
do repositório. O caminho para rodar o projeto do zero MUST estar documentado e ser
verificável com poucos comandos. Dependências Python MUST ser gerenciadas com `uv` e
versões fixadas em lockfile.

**Razão**: quem avalia o portfólio precisa conseguir rodar o projeto sem ajuda.

### VI. Código Original e Dados Públicos

Todo código MUST ser escrito do zero. É proibido reutilizar código, nomes, regras de
negócio ou dados de qualquer empregador; o projeto do trabalho serve só como referência
de padrões gerais. O projeto MUST usar apenas dados públicos, respeitando as licenças
(SCR.data: ODbL, com atribuição no README).

**Razão**: o repositório é público e representa capacidade técnica própria.

### VII. Documentação Faz Parte da Entrega

Cada fatia MUST atualizar o README (como rodar, o que a fatia entrega). Decisões de
arquitetura relevantes MUST ser registradas como ADR curto em `docs/adr/`. Uma fatia sem
documentação não está concluída.

**Razão**: em portfólio, o que não está documentado não é percebido.

## Restrições Técnicas

- Linguagem: Python 3.13; SQL para silver e gold.
- Camadas: bronze em Parquet (arquivos locais) → silver em PostgreSQL (limpo e tipado) →
  gold em modelos dbt (dimensional).
- Orquestração: Airflow, a partir da fatia "Airflow + dbt". Antes disso, o pipeline roda
  por CLI.
- CI: GitHub Actions rodando lint e testes a cada push, a partir da fatia "CI".
- Fontes: BCB SGS (séries 432, 433 e 1), BCB SCR.data, IBGE SIDRA. Chamadas às APIs MUST
  respeitar os limites de janela por requisição (paginar por período), com retry e timeout.
- Segredos e credenciais MUST ficar em `.env` (fora do git), com `.env.example` versionado.
- Ambiente de desenvolvimento: Windows. Scripts e comandos documentados MUST funcionar no
  Windows ou rodar dentro de containers.

## Fluxo de Trabalho

- Mudanças MUST ficar dentro do escopo do `tasks.md` da spec ativa. Problemas encontrados
  fora do escopo são reportados ao autor, não corrigidos.
- O agente MUST NOT dar push, abrir PR, nem editar changelog ou versão sem pedido explícito.
  A publicação no GitHub é feita pelo autor.
- Cada feature trabalha em branch própria criada pelo fluxo do Spec Kit; commits pequenos,
  com mensagens descritivas.
- Uma fatia só é dada como concluída quando: testes passam, o pipeline roda do zero e a
  documentação está atualizada.

## Governance

Esta constitution prevalece sobre outras práticas do projeto. O `Constitution Check` de
cada `plan.md` MUST verificar conformidade com os princípios acima; violações só são
aceitas se justificadas na tabela Complexity Tracking do plano.

Emendas são feitas via `/speckit-constitution`, com Sync Impact Report e propagação para os
templates afetados. Versionamento semântico: MAJOR para remoção ou redefinição de
princípio; MINOR para princípio ou seção nova, ou expansão material; PATCH para
esclarecimentos e redação. Orientações de runtime ficam em `CLAUDE.md`.

**Version**: 1.0.0 | **Ratified**: 2026-10-04 | **Last Amended**: 2026-10-04
