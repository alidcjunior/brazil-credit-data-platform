# Fixtures da API BCB SGS

Respostas reais da API, gravadas em 2026-10-04, usadas pelos testes unitários (sem rede).
Base: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json`

| Arquivo | Consulta | Observação |
|---|---|---|
| `sgs_432_2012-06-01_2012-07-31.json` | série 432, `dataInicial=01/06/2012&dataFinal=31/07/2012` | meta Selic diária; muda de 8,50 para 8,00 em 12/07/2012 |
| `sgs_433_2011-06-01_2012-12-01.json` | série 433, `dataInicial=01/06/2011&dataFinal=01/12/2012` | IPCA mensal, datado no dia 1 |
| `sgs_432_406_window_too_large.json` | série 432, `dataInicial=01/06/2012&dataFinal=01/10/2026` | HTTP 406: janela acima de 10 anos em série diária |
| `sgs_432_200_html_invalid_request.html` | série 432, `dataInicial=01/06/2012&dataFinal=31/05/2022` | HTTP 200 com página HTML "Requisição inválida!" após ~30 s; erro transitório (a mesma consulta, repetida, volta JSON) |
