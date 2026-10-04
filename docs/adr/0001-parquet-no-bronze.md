# ADR-0001: Parquet imutável por execução no bronze

- **Status**: aceito
- **Data**: 2026-10-04
- **Fatia**: 1 (Selic e IPCA)

## Contexto

As fontes do Banco Central revisam dados retroativamente e a API SGS é instável: às vezes demora
cerca de 30 s e responde HTTP 200 com uma página HTML de erro. O pipeline precisa:

- reprocessar silver e gold a qualquer momento, sem depender da API estar no ar;
- saber exatamente o que a fonte respondeu em cada captura (auditoria de revisões);
- nunca expor uma captura que falhou no meio.

## Decisão

O bronze guarda as respostas da API **sem conversão**, em Parquet, **um diretório por execução**:

```text
data/bronze/bcb_sgs/serie=<codigo>/run=<run_id>/
├── part-000.parquet   # campos `data` e `valor` como string + metadados da requisição
└── manifest.parquet   # uma linha por janela consultada: URL, status, contagem, SHA-256 do corpo
```

- A escrita vai para `.tmp-run=<run_id>/` e só é renomeada no fim; leitores ignoram `.tmp-*`.
- Execuções existentes nunca são reescritas (`FileExistsError`).
- O silver lê todas as execuções e, para a mesma série e data, fica com a captura mais recente.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Guardar o JSON cru em arquivos `.json` | Mais fiel byte a byte, mas perde o formato colunar da arquitetura; o manifesto guarda o SHA-256 do corpo para rastreio |
| Sobrescrever uma partição por data de referência | Perde o histórico de revisões e quebra a imutabilidade |
| Converter tipos já no bronze | Um erro de parse perderia o dado original; a conversão fica no silver, onde falha apontando o `run_id` |
| Carregar direto da API no Postgres | Reprocessar exigiria a API no ar, e não haveria registro do que a fonte respondeu |

## Consequências

- Reprocessar silver e gold não precisa de rede.
- O volume cresce a cada execução: na Fatia 1 são cerca de 5,4 mil linhas por captura completa, o que é desprezível. A janela de repescagem da próxima fatia vai reduzir o período recapturado.
- Uma janela vazia continua registrada no manifesto, então "a fonte não tinha dado" é diferente de "não consultamos".
