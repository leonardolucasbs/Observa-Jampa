# Itinerário · Qualidade do ar

Coleta dados horários de qualidade do ar de João Pessoa (PB) e de outras capitais, que servem de comparação, na [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api). Os dados ficam num SQLite local e aparecem num dashboard Streamlit.

Este é o primeiro módulo do sistema de dados ambientais de João Pessoa. Resíduos e calor entram depois como novas fontes.

> Os valores são **estimativas do modelo CAMS** (Copernicus), não medições de sensores.

## Instalação

Pré-requisito: [uv](https://docs.astral.sh/uv/). O próprio uv baixa o Python 3.12.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
cd C:\Users\Leona\dev\itinerario\poluentes
uv sync
copy .env.example .env
```

As configurações ficam em `config.toml`: URL da API, fuso, localizações, janela de coleta, timeout/retry, diretrizes da OMS e textos do dashboard. O `.env` é opcional e sobrescreve `ITINERARIO_CONFIG`, `ITINERARIO_DB_PATH` e `ITINERARIO_LOG_LEVEL`.

## Uso

```powershell
uv run python -m itinerario.backfill --days 90
uv run python -m itinerario.collect
uv run streamlit run app.py
uv run pytest
```

| Comando | O que faz |
|---|---|
| `backfill --days N` | Carrega N dias de histórico mais 1 de previsão. A API aceita no máximo 92 dias em `past_days`; acima disso o backfill avisa no log e corta em 92. |
| `collect` | Busca as últimas 48 h mais 1 dia de previsão e faz UPSERT por (localização, hora). Os valores revisados pelo CAMS substituem os antigos sem duplicar registros. |
| `streamlit run app.py` | Abre o dashboard em http://localhost:8501. |

As quatro localizações vão numa única requisição, com as coordenadas separadas por vírgula. Erros de rede (timeout, 429 e 5xx) têm 3 tentativas com backoff exponencial. Se mesmo assim falhar, o script registra o erro no log e sai com código 1. O dashboard só lê o banco, então nunca quebra por falha de rede, e o botão "Atualizar dados agora" mostra o erro na barra lateral.

## Agendar a coleta horária no Windows

O `scripts\coletar.bat` roda a coleta e grava o log em `logs\coleta.log`.

**Pelo terminal** (PowerShell, sem precisar de admin):

```powershell
schtasks /Create /TN "Itinerario\ColetaArHoraria" /SC HOURLY /MO 1 /ST 00:05 /TR "\"C:\Users\Leona\dev\itinerario\poluentes\scripts\coletar.bat\"" /F
schtasks /Run /TN "Itinerario\ColetaArHoraria"
type C:\Users\Leona\dev\itinerario\poluentes\logs\coleta.log
```

**Pela interface** (Agendador de Tarefas → Criar Tarefa...):

1. **Geral:** nome `Itinerario - Coleta de ar`. Marque "Executar estando o usuário conectado ou não" se quiser que rode com a sessão bloqueada.
2. **Disparadores → Novo:** "Diariamente", início às 00:05, "Repetir a tarefa a cada: 1 hora" por "Indefinidamente".
3. **Ações → Novo:** "Iniciar um programa". Em Programa, `C:\Users\Leona\dev\itinerario\poluentes\scripts\coletar.bat`. Em "Iniciar em", `C:\Users\Leona\dev\itinerario\poluentes`.
4. **Configurações:** marque "Executar a tarefa assim que possível após uma inicialização agendada ser perdida".

O CAMS global atualiza duas vezes por dia, então a coleta de hora em hora sobra. O que ela garante é que os registros de previsão virem passado e que as revisões do CAMS entrem no banco.

## Arquitetura

```
src/itinerario/
├── config.py            config.toml + .env → Settings
├── bootstrap.py         composition root (monta client, repositórios e services)
├── domain/              Location, AirQualityReading, faixas EPA, poluente dominante
├── clients/             DataSourceClient (ABC), sessão HTTP com retry, client Open-Meteo + parser
├── repositories/        tabelas SQLAlchemy, UPSERT, consultas
├── services/            agregações (hora do dia, média diária, média por cidade) e AirQualityService
├── etl/                 pipeline fetch → upsert; jobs de collect/backfill
├── ui/                  componentes Streamlit + cache (st.cache_data)
├── collect.py           python -m itinerario.collect
└── backfill.py          python -m itinerario.backfill
app.py                   só monta a tela
```

**Para adicionar uma fonte nova** (ex.: calor):

1. Crie um client em `clients/` que implemente `DataSourceClient[T]`.
2. Crie a tabela e o repositório dela em `repositories/`.
3. Crie um service com as agregações em `services/`.
4. Crie um pipeline/job em `etl/`.
5. Crie os componentes da fonte em `ui/`.

O que já existe não precisa mudar.

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

## Atribuição

Dados de qualidade do ar: Open-Meteo, CAMS / Copernicus Atmosphere Monitoring Service — licença CC BY 4.0.
