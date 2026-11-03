# ObservaJP — Observatório Ambiental de João Pessoa

O ObservaJP é uma plataforma pública de inteligência ambiental urbana: uma aplicação web que reúne num só lugar dados de qualidade do ar, emissões de gases de efeito estufa, resíduos sólidos e outros indicadores ambientais de João Pessoa.

**Proposta de valor:** tornar acessíveis dados ambientais que hoje exigem consultar fontes diferentes, interpretar arquivos técnicos ou navegar por portais distintos.

## Páginas

Cada tema ambiental é uma página do app.

| Página | Situação | Pasta | Fonte dos dados |
|---|---|---|---|
| Poluentes (qualidade do ar) | Disponível | [`src/pages/poluentes/`](src/pages/poluentes/README.md) | Open-Meteo / CAMS (Copernicus) |
| Emissões de gases de efeito estufa | Planejada | — | — |
| Resíduos sólidos | Planejada | — | — |

## Como rodar

Pré-requisito: [uv](https://docs.astral.sh/uv/). O próprio uv baixa o Python 3.12. Rode os comandos na raiz do repositório:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv sync
uv run python -m pages.poluentes.backfill --days 90
uv run streamlit run src/app.py
```

O app abre em http://localhost:8501. O `backfill` só é necessário na primeira vez: ele carrega o histórico da qualidade do ar no banco local (`data/`, fora do git). Também dá para clicar em "Atualizar dados agora" na barra lateral da página.

Para rodar os testes de todas as páginas, use `uv run pytest`. A coleta agendada e a configuração de cada página estão no README da página.

## Arquitetura baseada em recursos

O código é organizado por recurso, não por camada. Cada página é uma pasta em `src/pages/` com a tela e todo o código de que ela precisa: clients, domínio, banco, serviços, componentes visuais e configuração. Para entender, mudar ou remover uma página, basta olhar uma pasta.

```
Observa-Jampa/
├── pyproject.toml              dependências do app inteiro (um projeto só)
├── uv.lock                     versões travadas
├── .env.example                variáveis opcionais que sobrescrevem as configs das páginas
├── scripts/                    tarefas agendadas (ex.: coletar_poluentes.bat)
├── data/                       bancos locais (fora do git)
├── logs/                       logs das coletas (fora do git)
├── src/
│   ├── app.py                  ponto de entrada: configura o app e o menu (st.navigation)
│   ├── .streamlit/             tema visual de todas as páginas
│   └── pages/
│       └── poluentes/          um recurso = uma pasta
│           ├── page.py         a tela
│           ├── config.toml     configurações da página
│           ├── clients/        acesso às APIs externas
│           ├── domain/         modelos e regras do tema
│           ├── repositories/   tabelas e consultas
│           ├── services/       agregações
│           ├── etl/            coleta → banco
│           └── ui/             componentes Streamlit
└── tests/
    └── poluentes/              testes do recurso
```

Regras do padrão:

- **Tudo da página fica na pasta dela.** O `page.py` só monta a tela com os componentes de `ui/`.
- **Uma página não importa código de outra.** Se duas páginas precisarem do mesmo código, ele sai das duas e vai para um pacote compartilhado em `src/` (ex.: `src/shared/`).
- **Os imports são absolutos a partir de `pages`**, por exemplo `from pages.poluentes.domain.models import Location`. O `src/pages/` é instalado como pacote pelo `uv sync`, então funciona no app, nos testes e na linha de comando.
- **Cada página fica numa subpasta, nunca como `.py` solto em `src/pages/`.** O Streamlit tem um modo antigo que lista no menu os `.py` soltos nessa pasta. Com subpastas, o menu fica só com o que está registrado no `app.py`.
- **O `app.py` só registra as páginas.** Nenhuma regra de negócio entra nele.

## Adicionar uma página

Exemplo com o tema `residuos`. Use o mesmo nome, em minúsculas e sem acento, na pasta, nos testes e no `url_path`.

1. **Crie a pasta do recurso** com um `__init__.py` vazio e o `page.py`:

   ```
   src/pages/residuos/
   ├── __init__.py
   ├── page.py
   ├── clients/  domain/  repositories/  services/  etl/  ui/   (cada uma com __init__.py)
   └── config.toml
   ```

   Crie só as subpastas de que a página precisar. Uma página com dados estáticos pode ter apenas `page.py` e `domain/`, por exemplo. Para uma página com coleta, use `src/pages/poluentes/` como modelo.

2. **Instale as bibliotecas novas**, se houver: `uv add <biblioteca>`. Elas entram no `pyproject.toml` e no `uv.lock` da raiz.

3. **Registre a página** em `PAGES` no `src/app.py`:

   ```python
   PAGES = {
       "Meio ambiente": [
           st.Page("pages/poluentes/page.py", title="Poluentes", icon="🌫️", url_path="poluentes", default=True),
           st.Page("pages/residuos/page.py", title="Resíduos sólidos", icon="♻️", url_path="residuos"),
       ],
   }
   ```

   O `url_path` é obrigatório: sem ele, todas as páginas tentariam usar o endereço `page`, que vem do nome do arquivo. As chaves de `PAGES` são as seções do menu.

4. **Crie os testes** em `tests/residuos/`, com `__init__.py`.

Com uma página só, o Streamlit esconde o menu de navegação. Ele aparece na barra lateral quando a segunda página é registrada.

## Tema visual

As cores e a fonte ficam em `src/.streamlit/config.toml` (tema claro, azul `#1D4899` como cor principal) e valem para todas as páginas. O Streamlit lê a pasta `.streamlit/` que está ao lado do `app.py`, então o tema funciona seja qual for a pasta de onde o app é aberto.

## Fontes e atribuição

| Tema | Fonte | Licença |
|---|---|---|
| Qualidade do ar | Open-Meteo, CAMS / Copernicus Atmosphere Monitoring Service | CC BY 4.0 |

Os valores de qualidade do ar são estimativas do modelo CAMS, não medições de sensores locais.

## Licença

[MIT](LICENSE).
