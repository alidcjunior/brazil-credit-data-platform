# Feature Specification: Fatia 1 — Selic e IPCA ponta a ponta

**Feature Branch**: `001-selic-ipca-slice`
**Created**: 2026-10-04
**Status**: Draft
**Input**: User description: "Fatia 1: Selic e IPCA ponta a ponta. Ingerir as séries do BCB SGS 432
(meta Selic, diária) e 433 (IPCA mensal) via API REST, paginando por período respeitando o limite
de janela por requisição; gravar a resposta bruta em bronze (Parquet imutável, com metadados de
extração); carregar em silver (PostgreSQL, tipado, upsert por chave natural); produzir uma camada
gold com visão mensal combinando Selic (média/fim de mês) e IPCA (mensal e acumulado 12 meses); e
gerar um gráfico que mostre a relação Selic x IPCA ao longo do tempo. Carga inicial a partir de
jun/2012 (alinhado ao SCR.data). Tudo roda com Docker Compose (Postgres) e uma CLI; testes
automatizados desde já (fixtures offline das respostas reais, teste de idempotência da carga,
testes de dados no gold). Fora do escopo desta fatia: carga incremental com janela de repescagem,
CI, Airflow, dbt, SCR.data, IBGE e dashboard."

## User Scenarios & Testing *(mandatory)*

Ator principal: o **operador do pipeline** (o autor ou alguém avaliando o portfólio), que roda o
projeto a partir do repositório. Ator secundário: o **leitor da análise**, que consome a visão
mensal e o gráfico.

### User Story 1 - Capturar o histórico bruto das séries (Priority: P1)

O operador executa um único comando informando o período desejado e o sistema baixa, da fonte
oficial do Banco Central, o histórico completo da meta Selic e do IPCA mensal, guardando uma
cópia fiel e imutável de cada resposta, junto com quando e como ela foi obtida.

**Why this priority**: sem a captura bruta nada mais existe; a cópia imutável permite reprocessar
tudo depois sem depender da fonte estar no ar.

**Independent Test**: rodar a captura para o período completo e verificar que existem registros
brutos para as duas séries cobrindo todo o período, cada um com seus metadados de extração.

**Acceptance Scenarios**:

1. **Given** nenhum dado capturado, **When** o operador pede a captura de jun/2012 até hoje
   (IPCA desde jun/2011, para o acumulado 12m),
   **Then** o sistema guarda as respostas brutas das duas séries cobrindo todo o período, mesmo
   que a fonte limite o tamanho de cada consulta.
2. **Given** uma captura já feita, **When** o operador captura de novo o mesmo período, **Then** a
   captura anterior permanece intacta e a nova é guardada separadamente.
3. **Given** a fonte fora do ar ou respondendo erro, **When** o operador pede a captura, **Then**
   o sistema tenta novamente um número limitado de vezes e, persistindo a falha, termina com
   mensagem clara e sem gravar captura parcial como se fosse completa.

---

### User Story 2 - Disponibilizar as séries limpas e tipadas (Priority: P1)

O operador executa a carga e o sistema transforma as capturas brutas em séries limpas: datas e
valores numéricos tipados, uma linha por série e data, prontas para consulta.

**Why this priority**: é a base confiável sobre a qual a visão analítica é construída; junto com
a US1 forma o mínimo demonstrável de ingestão.

**Independent Test**: carregar a partir de capturas brutas gravadas (sem acesso à fonte) e
verificar tipos, contagem de linhas e ausência de duplicatas; rodar a carga duas vezes e
confirmar que o estado final é idêntico.

**Acceptance Scenarios**:

1. **Given** capturas brutas das duas séries, **When** o operador executa a carga, **Then** cada
   observação aparece uma única vez, identificada por série e data, com valor numérico.
2. **Given** a carga já executada, **When** o operador executa a mesma carga de novo, **Then** o
   conteúdo das séries limpas fica idêntico (nenhuma linha duplicada, alterada ou perdida).
3. **Given** uma captura mais recente que traz valor diferente para uma data já carregada,
   **When** a carga é executada, **Then** prevalece o valor da captura mais recente.

---

### User Story 3 - Visão mensal Selic x IPCA (Priority: P2)

O leitor da análise consulta uma visão mensal que, para cada mês desde jun/2012, mostra a meta
Selic média do mês, a meta Selic no último dia do mês, o IPCA do mês e o IPCA acumulado em 12
meses.

**Why this priority**: é a resposta analítica da fatia e a base para cruzar com crédito nas
próximas fatias; depende de US1 e US2.

**Independent Test**: construir a visão a partir de séries limpas conhecidas e comparar os
indicadores de meses escolhidos com valores calculados à mão e com valores publicados pelo BCB/IBGE.

**Acceptance Scenarios**:

1. **Given** as séries limpas, **When** a visão mensal é gerada, **Then** existe exatamente uma
   linha por mês de jun/2012 até o último mês com IPCA publicado.
2. **Given** um mês qualquer, **When** o leitor consulta a visão, **Then** o IPCA acumulado em
   12 meses corresponde à composição dos 12 IPCAs mensais terminando naquele mês.
3. **Given** a visão gerada duas vezes a partir das mesmas séries limpas, **Then** o resultado é
   idêntico.

---

### User Story 4 - Gráfico Selic x IPCA (Priority: P3)

O leitor da análise vê um gráfico com a evolução mensal da meta Selic e do IPCA acumulado em 12
meses no mesmo eixo de tempo, gerado a partir da visão mensal com um comando.

**Why this priority**: torna o resultado da fatia visível para quem avalia o portfólio; é a
última etapa e depende da visão mensal.

**Independent Test**: gerar o gráfico a partir da visão mensal e verificar que o arquivo é
produzido, cobre todo o período e tem título, legenda, eixos rotulados e indicação de fonte.

**Acceptance Scenarios**:

1. **Given** a visão mensal pronta, **When** o operador gera o gráfico, **Then** é produzido um
   arquivo de imagem com as duas séries de jun/2012 até o último mês disponível.
2. **Given** o gráfico gerado, **When** o leitor o abre, **Then** identifica cada série pela
   legenda, as unidades (% a.a. e % em 12 meses) e a fonte dos dados.

---

### Edge Cases

- A fonte limita consultas de séries diárias a janelas de no máximo 10 anos: o período pedido
  precisa ser dividido, sem buracos nem sobreposição entre os pedaços.
- A meta Selic tem valor em todos os dias corridos; o IPCA tem um valor por mês, datado no dia 1.
- O mês corrente pode ter Selic e ainda não ter IPCA publicado: a visão mensal termina no último
  mês com IPCA disponível.
- Para os 11 primeiros meses da janela (jun/2012 em diante), o acumulado em 12 meses exige IPCA
  anterior a jun/2012: a captura do IPCA começa 12 meses antes do período de análise.
- A fonte responde com resposta vazia, malformada ou valor não numérico: a carga falha de forma
  explícita, apontando a captura problemática, em vez de gravar dado inválido.
- Período pedido inválido (data inicial depois da final, ou no futuro): o comando recusa com
  mensagem clara antes de chamar a fonte.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST capturar a meta Selic (série SGS 432) e o IPCA mensal (série SGS 433)
  diretamente da fonte oficial do Banco Central, para um período informado pelo operador.
- **FR-002**: O sistema MUST dividir automaticamente períodos longos em consultas que respeitem o
  limite de janela da fonte, cobrindo o período inteiro sem lacunas nem sobreposição.
- **FR-003**: O sistema MUST guardar cada resposta da fonte exatamente como recebida, junto com
  série, período consultado e momento da extração; capturas guardadas nunca são alteradas ou
  sobrescritas.
- **FR-004**: O sistema MUST repetir consultas que falharem por erro transitório, com número
  limitado de tentativas, e encerrar com erro claro se a falha persistir.
- **FR-005**: O sistema MUST produzir séries limpas com data e valor numérico tipados, uma
  observação por série e data.
- **FR-006**: A carga das séries limpas MUST ser idempotente: executá-la novamente com as mesmas
  capturas resulta exatamente no mesmo conteúdo.
- **FR-007**: Quando houver mais de uma captura para a mesma série e data, o valor da captura mais
  recente MUST prevalecer.
- **FR-008**: O sistema MUST produzir uma visão mensal de jun/2012 em diante com: Selic média do
  mês, Selic no último dia do mês, IPCA do mês e IPCA acumulado em 12 meses (composto).
- **FR-009**: O sistema MUST gerar um gráfico de evolução mensal da Selic e do IPCA acumulado em
  12 meses a partir da visão mensal, com título, legenda, unidades e fonte.
- **FR-010**: O operador MUST conseguir executar cada etapa (captura, carga, visão mensal,
  gráfico) separadamente e o fluxo completo com um único comando.
- **FR-011**: O sistema MUST validar a visão mensal com verificações automáticas de dados: um mês
  por linha, sem valores ausentes nos indicadores e valores dentro de faixas plausíveis.
- **FR-012**: Todo o fluxo MUST poder ser executado do zero em uma máquina nova, seguindo apenas
  as instruções do README.
- **FR-013**: As verificações automáticas de captura e carga MUST rodar sem acesso à internet,
  usando respostas reais da fonte previamente gravadas.

### Key Entities *(include if feature involves data)*

- **Captura bruta**: uma resposta da fonte como recebida. Atributos: série, período consultado,
  momento da extração, conteúdo original. Imutável.
- **Observação de série**: um valor de uma série numa data. Atributos: série, data, valor,
  captura de origem. Identificada por série + data.
- **Indicador mensal**: um mês da visão analítica. Atributos: mês de referência, Selic média,
  Selic de fim de mês, IPCA do mês, IPCA acumulado 12 meses. Identificado pelo mês.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A partir de um clone limpo do repositório, o operador obtém o gráfico final em até
  15 minutos seguindo apenas o README (excluindo download de ferramentas).
- **SC-002**: O fluxo completo para jun/2012 até hoje termina em até 5 minutos numa máquina comum.
- **SC-003**: 100% dos meses de jun/2012 até o último IPCA publicado aparecem na visão mensal,
  sem lacunas.
- **SC-004**: Para pelo menos 3 meses de checagem, o IPCA acumulado em 12 meses difere no máximo
  0,01 ponto percentual do valor publicado oficialmente.
- **SC-005**: Executar o fluxo completo duas vezes seguidas produz resultados idênticos (zero
  linhas duplicadas ou alteradas).
- **SC-006**: As verificações automáticas rodam sem internet e terminam em menos de 1 minuto.

## Assumptions

- Período de análise começa em jun/2012 para alinhar com o SCR.data; o IPCA é capturado desde
  jun/2011 apenas para viabilizar o acumulado em 12 meses no início da série.
- "Selic" nesta fatia é a meta definida pelo Copom (série 432), em % ao ano; a Selic efetiva fica
  fora do escopo.
- O gráfico é um arquivo de imagem estático gerado por comando; dashboard interativo fica para a
  fatia de dashboard.
- Cada execução recaptura o período pedido inteiro; carga incremental com janela de repescagem é
  a próxima fatia.
- O banco roda em Docker Compose; o desenvolvimento pode começar sem Docker (captura e testes
  offline), mas a fatia só é concluída depois de rodar com ele. Execução por CLI, sem
  orquestrador nesta fatia.
- A API do SGS é pública e não exige autenticação.
- Fora do escopo: CI, Airflow, dbt, SCR.data, IBGE, câmbio (série 1) e dashboard.
