# Chuvas e alertas · Previsão de chuva e avisos meteorológicos

Página do [ObservaJP](../../../README.md) com a previsão de chuva e o acompanhamento dos avisos meteorológicos oficiais para João Pessoa. Mostra quanto chove previsto hoje, amanhã e nos próximos 7 dias e lista os avisos do INMET vigentes ou futuros que abrangem o município.

> É previsão, não chuva medida, e não prevê alagamento em ruas específicas: para isso seriam necessários registros de ocorrências, sensores ou um modelo de risco validado. Um aviso do INMET indica condição meteorológica de risco, não confirma alagamento. A ausência de avisos não significa ausência de risco.

## Comandos

Rode na raiz do repositório:

```powershell
uv run pytest tests/chuvas
uv run streamlit run src/app.py
```

A página fica em http://localhost:8501/chuvas. Não precisa de chave, banco nem coleta agendada: as fontes são consultadas pelo servidor do Streamlit quando alguém abre a página e o cache venceu.

Os testes não acessam a rede. Usam respostas reais gravadas em `tests/chuvas/fixtures/` (10/11/2026) e dublês para simular timeout, HTTP 429/503, formato inesperado e avisos para João Pessoa (nenhum aviso real desse dia abrangia a cidade).

## Fontes

| Dado | Endpoint | Fonte |
|---|---|---|
| Chuva prevista por dia | `https://api.open-meteo.com/v1/forecast?latitude=-7.1195&longitude=-34.845&daily=precipitation_sum,precipitation_probability_max&hourly=precipitation&forecast_days=7&timezone=America/Fortaleza` | [Open-Meteo Forecast API](https://open-meteo.com/en/docs), CC BY 4.0 |
| Avisos meteorológicos | `https://apiprevmet3.inmet.gov.br/avisos/ativos` | INMET, Instituto Nacional de Meteorologia |
| Página de cada aviso | `https://avisos.inmet.gov.br/{id}` | INMET (é o campo `<web>` do CAP do aviso) |

As duas fontes são independentes: cada uma tem sessão HTTP, cache e prazos próprios, e cada seção da tela é um fragment executado em paralelo. Se uma cair, a outra continua aparecendo normalmente.

## Como os acumulados são calculados

1. A Open-Meteo é consultada no fuso `America/Fortaleza`, então cada data de `daily.time` é um dia local de João Pessoa (0h a 24h). A resposta é recusada se vier em outro fuso.
2. "Hoje" é a data atual em João Pessoa, não em UTC. Às 22h30 de 10/11 em João Pessoa já é 11/11 em UTC, e a página continua mostrando 10/11.
3. Cada dia usa `daily.precipitation_sum`. Se a fonte não trouxer o total de um dia, ele é a soma de `hourly.precipitation`, mas só se as 24 horas vierem preenchidas. A tela avisa quando o total veio das horas. Na resposta real, as duas contas dão o mesmo valor.
4. **Hoje** e **Amanhã** são o total de um dia. **Próximos 7 dias** é a soma dos totais diários de hoje até hoje + 6. Os dias são localizados pela data, não pela posição na resposta, e entram uma vez cada. Uma previsão do cache consultada ontem ainda serve para hoje, e o dia que falta aparece como faltante.
5. Valor ausente, nulo, negativo ou que não é número fica como **sem dado**, nunca como zero. O card mostra "—" e "Sem dado de previsão". Se faltar algum dia na semana, o acumulado aparece como **parcial**, com os dias que faltam.
6. `precipitation_probability_max` aparece separada, como "até X% em alguma hora do dia (não é volume)". Probabilidades nunca são somadas.

## Como os avisos são filtrados para João Pessoa

O endpoint não tem documentação pública. O formato abaixo foi validado com requisições reais em 10/11/2026:

```
{"hoje": [aviso, ...], "futuro": [aviso, ...]}
```

| Campo | Uso |
|---|---|
| `id`, `id_aviso`, `id_sequencia` | identificação. O mesmo aviso aparece em "hoje" e em "futuro" (é contado uma vez), e uma sequência maior do mesmo `id_aviso` substitui a anterior |
| `descricao` | fenômeno ("Chuvas Intensas", "Acumulado de Chuva", "Tempestade"...) |
| `severidade`, `aviso_cor` | nível e cor oficiais ("Perigo Potencial" #FFFE00, "Perigo" #F96602...). A página usa a cor da fonte e não cria níveis |
| `inicio`, `fim` | "AAAA-MM-DD HH:MM" em horário de Brasília. O fuso foi conferido com `onset`/`expires` do CAP do mesmo aviso (`-03:00`). Na falta deles, usa `data_inicio` + `hora_inicio` |
| `encerrado` | aviso encerrado antes do fim previsto: sai da lista |
| `geocodes`, `municipios` | códigos IBGE dos municípios abrangidos |
| `mesorregioes`, `estados` | área do aviso, mostrada no card |
| `riscos`, `instrucoes` | listas de textos oficiais, mostradas como vieram |

1. **Abrangência:** o aviso abrange João Pessoa se o código IBGE `2507507` está em `geocodes` ou entre os códigos de `municipios` ("João Pessoa - PB (2507507)"). O nome sozinho não basta, porque há municípios homônimos em outros estados. A geometria (`poligono`) não é usada: a lista de municípios é a do próprio INMET e cobre o município inteiro, não só um ponto.
2. **Situação**, calculada a cada exibição (um aviso do cache que terminou sai na hora): **futuro** antes do início, **vigente** entre início e fim, **expirado** depois do fim ou se `encerrado`. Expirados não aparecem. Sem início ou fim legíveis, o aviso aparece como "validade não informada".
3. Vigentes vêm primeiro, depois os futuros, por ordem de início.
4. Avisos sem nenhuma lista de municípios, ou itens ilegíveis, não podem ser conferidos. A tela informa quantos foram e indica o mapa oficial.
5. Se a resposta não tiver as listas `hoje` e `futuro`, ela é tratada como erro, e não como "nenhum aviso". Só se afirma que não há avisos com a lista em mãos.

### RSS e CAP

O feed `https://apiprevmet3.inmet.gov.br/avisos/rss` (RSS 2.0) também funciona, mas lista cerca de 90 itens, incluindo expirados, e informa a área só por mesorregião. Para saber se um item abrange João Pessoa é preciso baixar o CAP de cada aviso (`/avisos/rss/{id}`, CAP 1.2 com `onset`, `expires`, `severity` e a lista de municípios com código IBGE), ou seja, uma requisição por aviso. Por isso o JSON `/avisos/ativos`, que traz tudo numa requisição, é a fonte usada. O CAP foi usado para confirmar o fuso dos horários e o link oficial de cada aviso. Se o JSON deixar de existir, o caminho validado é: RSS → filtrar por mesorregiões da Paraíba → CAP só desses avisos.

## Atualização e cache

| | Open-Meteo | INMET |
|---|---|---|
| Nova consulta no máximo a cada | 30 min | 10 min |
| Última resposta válida exibida, marcada como desatualizada, por até | 6 h | 2 h |
| Espera depois de uma falha | 2 min (ou o `Retry-After` do HTTP 429, se maior) | 2 min (idem) |
| Timeout por requisição | 10 s, 1 nova tentativa para 5xx e falhas de conexão | 10 s, idem |

- O cache (`services/cache.py`) fica no processo do Streamlit e é compartilhado por todas as sessões: dez pessoas com a página aberta geram uma consulta por intervalo, não dez. Enquanto uma consulta está em andamento, as outras sessões esperam o mesmo resultado.
- A tela se redesenha sozinha a cada 5 min (`st.fragment(run_every=...)`). Redesenhar não consulta as fontes: só o fim do intervalo de cada uma consulta.
- Cada seção mostra a fonte, a data e a hora da **última consulta bem-sucedida** e o estado: *consultado agora*, *em cache, consultado há X min* ou *desatualizado*. Quando desatualizado, um aviso amarelo aparece antes dos dados. Passado o prazo máximo, os dados deixam de aparecer e a seção mostra o erro.
- O horário da consulta é diferente do período a que o valor se refere: cada card informa o dia ou o intervalo da previsão, e cada aviso informa início e término.
- HTTP 429 não é repetido na hora. O cache espera o `Retry-After` antes de tentar de novo.
- Não há banco de dados: a funcionalidade não precisa guardar histórico.

## Limitações das fontes

- **Open-Meteo:** é previsão de modelo numérico para uma célula de grade (a resposta indica -7,14; -34,84, 38 m de altitude), não medição. O total de hoje inclui as horas que já passaram, também previstas, não observadas. A resposta não informa o horário da rodada do modelo, por isso a tela mostra o horário da consulta e o período da previsão. Os valores mudam ao longo do dia: entre duas consultas com 10 min de intervalo em 10/11/2026, o total de hoje passou de 3,8 para 4,0 mm. O uso gratuito é não comercial e tem limite diário de requisições.
- **INMET `/avisos/ativos`:** não tem documentação nem contrato de estabilidade. O formato pode mudar sem aviso, e o parser recusa o que não reconhece em vez de mostrar uma lista vazia. Os horários vêm sem fuso explícito (`data_inicio` termina em `Z`, mas só a data é válida). A resposta tem cerca de 250 KB, quase tudo ícones e polígonos. Numa das requisições de teste, feita sem User-Agent identificado, o servidor encerrou a conexão; com o User-Agent do app, todas responderam.
- **Avisos e alagamentos:** os avisos cobrem regiões inteiras. Eles não dizem em que ruas ou bairros vai alagar.

## Configuração

Tudo fica em `config.toml`, nesta pasta: coordenadas e código IBGE, fuso, URLs, timeouts, intervalos de atualização, prazos de dados desatualizados e textos da tela. Não há variáveis de ambiente nem segredos.

## Arquitetura

```
src/pages/chuvas/
├── page.py              a tela: duas seções (fragments paralelos com atualização automática)
├── bootstrap.py         composition root (clients, caches e services de cada fonte)
├── config.toml          configurações da página
├── config.py            config.toml → Settings
├── clients/             sessão HTTP, Open-Meteo (previsão) e INMET (avisos), com a validação das respostas
├── domain/              modelos, acumulados de chuva e regras dos avisos (situação, abrangência, versões)
├── services/            cache com frescor (atual / em cache / desatualizado) e os services de chuva e de avisos
└── ui/                  cards de chuva, cards de aviso, origem e frescor dos dados, formatação e cores
```
