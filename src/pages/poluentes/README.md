# Poluentes · Qualidade do ar

Página do [ObservaJP](../../../README.md) sobre a qualidade do ar de João Pessoa (PB). Ela coleta dados horários da cidade e de outras capitais, que servem de comparação, na [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), guarda tudo num SQLite local e mostra num dashboard.

Foi o primeiro recurso do ObservaJP e serve de modelo para os próximos. Tudo o que a página usa está nesta pasta.

> Os valores são **estimativas do modelo CAMS** (Copernicus), não medições de sensores.

## Configuração

As configurações ficam em `config.toml`, nesta pasta: URL da API, fuso, localizações, janela de coleta, timeout/retry, diretrizes da OMS e textos do dashboard.

O `.env` na raiz do repositório é opcional e sobrescreve `POLUENTES_CONFIG`, `POLUENTES_DB_PATH` e `POLUENTES_LOG_LEVEL`. Há um modelo em `.env.example`. Caminhos relativos partem da raiz do repositório. O banco padrão é `data/poluentes.db`.

## Comandos

Rode os comandos na raiz do repositório:

```powershell
uv run python -m pages.poluentes.backfill --days 90
uv run python -m pages.poluentes.collect
uv run pytest tests/poluentes
uv run streamlit run src/app.py
```

| Comando | O que faz |
|---|---|
| `backfill --days N` | Carrega N dias de histórico mais 1 de previsão. A API aceita no máximo 92 dias em `past_days`; acima disso o backfill avisa no log e corta em 92. |
| `collect` | Busca as últimas 48 h mais 1 dia de previsão e faz UPSERT por (localização, hora). Os valores revisados pelo CAMS substituem os antigos sem duplicar registros. |
| `pytest tests/poluentes` | Roda os testes desta página. |
| `streamlit run src/app.py` | Abre o app. Esta página fica em http://localhost:8501/poluentes. |

As quatro localizações vão numa única requisição, com as coordenadas separadas por vírgula. Erros de rede (timeout, 429 e 5xx) têm 3 tentativas com backoff exponencial. Se mesmo assim falhar, o script registra o erro no log e sai com código 1. O dashboard só lê o banco, então nunca quebra por falha de rede, e o botão "Atualizar dados agora" mostra o erro na barra lateral.

## O dashboard

A tela tem duas abas:

- **Resumo** (aberta por padrão) é para quem não é da área. Responde em linguagem simples: *o ar está bom agora?* (cartão colorido com escala de 0 a 500), *como foi nos últimos dias?* (calendário) e *como estão as outras capitais?*.
- **Detalhes técnicos** traz os gráficos em µg/m³ (tendência com diretrizes da OMS, padrão por hora, comparativo e mapa).

Os textos em linguagem simples de cada faixa ficam em `domain/guidance.py`. No `config.toml`, `plain_disclaimer` é o aviso sobre a origem dos dados que aparece no Resumo.

As cores e a fonte vêm do tema do app, em `src/.streamlit/config.toml`.

## Agendar a coleta horária no Windows

O `scripts\coletar_poluentes.bat`, na raiz do repositório, roda a coleta e grava o log em `logs\coleta_poluentes.log`.

**Pelo terminal** (PowerShell, sem precisar de admin). Troque `$repo` pelo caminho do repositório na sua máquina:

```powershell
$repo = "C:\caminho\para\Observa-Jampa"
schtasks /Create /TN "ObservaJP\ColetaPoluentes" /SC HOURLY /MO 1 /ST 00:05 /TR "$repo\scripts\coletar_poluentes.bat" /F
schtasks /Run /TN "ObservaJP\ColetaPoluentes"
Get-Content "$repo\logs\coleta_poluentes.log" -Tail 20
```

Se o caminho tiver espaços, use a interface abaixo.

**Pela interface** (Agendador de Tarefas → Criar Tarefa...):

1. **Geral:** nome `ObservaJP - Coleta de poluentes`. Marque "Executar estando o usuário conectado ou não" se quiser que rode com a sessão bloqueada.
2. **Disparadores → Novo:** "Diariamente", início às 00:05, "Repetir a tarefa a cada: 1 hora" por "Indefinidamente".
3. **Ações → Novo:** "Iniciar um programa". Em Programa, `<repo>\scripts\coletar_poluentes.bat`. Em "Iniciar em", `<repo>`.
4. **Configurações:** marque "Executar a tarefa assim que possível após uma inicialização agendada ser perdida".

O CAMS global atualiza duas vezes por dia, então a coleta de hora em hora sobra. O que ela garante é que os registros de previsão virem passado e que as revisões do CAMS entrem no banco.

## Arquitetura

```
src/pages/poluentes/
├── page.py              a tela: só junta os componentes de ui/
├── config.toml          configurações da página
├── config.py            config.toml + .env → Settings
├── bootstrap.py         composition root (monta client, repositórios e services)
├── domain/              Location, AirQualityReading, faixas EPA, poluente dominante, textos simples
├── clients/             DataSourceClient (ABC), sessão HTTP com retry, client Open-Meteo + parser
├── repositories/        tabelas SQLAlchemy, UPSERT, consultas
├── services/            agregações (hora do dia, média diária, média por cidade) e AirQualityService
├── etl/                 pipeline fetch → upsert; jobs de collect/backfill
├── ui/                  componentes Streamlit + cache (st.cache_data)
├── collect.py           python -m pages.poluentes.collect
└── backfill.py          python -m pages.poluentes.backfill
```

Na escrita, o `etl` busca os dados pelos `clients` e grava pelos `repositories`. Na leitura, o `page.py` usa a `ui`, que consulta os `services`, que leem dos `repositories`. Todas as camadas usam o `domain`, e o `domain` não importa nenhuma delas.

**Para adicionar outra fonte de qualidade do ar** (ex.: estações de medição locais):

1. Crie um client em `clients/` que implemente `DataSourceClient[T]`.
2. Crie a tabela e o repositório dela em `repositories/`.
3. Crie um service com as agregações em `services/`.
4. Crie um pipeline/job em `etl/`.
5. Crie os componentes da fonte em `ui/`.

O que já existe não precisa mudar. Um tema novo (resíduos, emissões) não entra aqui: ele vira uma página própria em `src/pages/`, como explica a seção "Adicionar uma página" do [README da raiz](../../../README.md).

## Modelo de dados

| Tabela | Colunas |
|---|---|
| `location` | id, slug (único), name, latitude, longitude |
| `air_quality_measurement` | id, location_id, measured_at, us_aqi, european_aqi, pm2_5, pm10, nitrogen_dioxide, ozone, carbon_monoxide, sulphur_dioxide, dust, dominant_pollutant, is_forecast, fetched_at. Índice único em (location_id, measured_at). |

- `measured_at` e `fetched_at` são guardados em hora local `America/Fortaleza` (UTC−3, sem horário de verão).
- `dominant_pollutant` é o poluente com o maior sub-índice US AQI (`us_aqi_pm2_5`, `us_aqi_ozone` etc., que a API fornece).
- `is_forecast` marca as horas posteriores à hora da coleta.

## Referências usadas

- Diretrizes da OMS (2021) para média de 24 h: PM2.5 = 15 µg/m³ e NO₂ = 25 µg/m³. O gráfico compara com a **média diária**, não com o valor horário.
- Faixas e cores EPA do US AQI: 0–50 Boa, 51–100 Moderada, 101–150 Ruim p/ sensíveis, 151–200 Ruim, 201–300 Muito ruim, 301+ Perigosa.
- No calendário do Resumo, a cor de cada dia é a **mediana das classificações** horárias: cada hora observada recebe uma faixa EPA e o dia fica com a faixa do meio. Um dia completo tem 24 horas; se as duas faixas do meio forem diferentes, vale a pior.

## Atribuição

Dados de qualidade do ar: Open-Meteo, CAMS / Copernicus Atmosphere Monitoring Service — licença CC BY 4.0.
