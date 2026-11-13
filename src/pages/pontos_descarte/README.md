# Pontos de descarte · Eletroeletrônicos

Página do [ObservaJP](../../../README.md) que mostra num mapa onde descartar eletroeletrônicos em João Pessoa e região (Cabedelo e Santa Rita). A pessoa filtra pelo que quer descartar, por bairro e por endereço, abre os detalhes de cada ponto e vê a rota até o ponto mais próximo que aceita o seu item.

> As informações vêm de um mapa colaborativo e podem estar desatualizadas. A tela pede para confirmar horário e itens aceitos com o local.

## Comandos

Rode na raiz do repositório:

```powershell
uv run python -m pages.pontos_descarte.prepare
uv run pytest tests/pontos_descarte
uv run streamlit run src/app.py
```

| Comando | O que faz |
|---|---|
| `prepare` | Lê a planilha `data/pontos_descarte_eletroeletronicos_coordenadas_1.xlsx`, limpa os dados e completa bairro, endereço e cidade que faltam consultando o OpenStreetMap (Nominatim, 1 requisição por segundo, cerca de 1 minuto). Grava `data/pontos_descarte.json`. Também baixa o limite oficial de João Pessoa da API de malhas do IBGE para `data/limite_joao_pessoa.geojson` e os endereços do Censo 2022 (CNEFE/IBGE) para o índice de endereços `data/enderecos.sqlite`. Os três arquivos vão para o git. Rode de novo sempre que a planilha mudar; `--so pontos`, `--so limite` ou `--so enderecos` gera só uma das partes. |
| `pytest tests/pontos_descarte` | Testes da página. Não acessam a rede: os serviços externos são substituídos por dublês e por respostas reais gravadas em `tests/pontos_descarte/fixtures/`. |
| `streamlit run src/app.py` | Abre o app. Esta página fica em http://localhost:8501/pontos_descarte. |

A página só lê os arquivos de `data/`, então abre mesmo sem internet. A rede só é usada quando a pessoa pede algo que depende dela: localizar um bairro ou um lugar que não está nos dados, ou calcular uma rota. Endereços com rua e número são localizados no índice do IBGE, sem rede.

## Como a busca entende o texto

Os três campos aceitam texto livre e não exigem o nome exato.

**O que você quer descartar?** Um vocabulário em `domain/waste.py` liga objetos do dia a dia às categorias da planilha. "geladeira" vira eletrodoméstico de grande porte, "fone de ouvido" vira acessório de celular, "lixo eletrônico" significa qualquer ponto. Com mais de um item ("notebook e pilhas"), o ponto precisa aceitar todos. Se nada for reconhecido, as palavras são procuradas na descrição e nas observações dos pontos.

Cada ponto recebe um selo:

- **Aceita**: a descrição do ponto cobre o item.
- **Confirmar com o local**: o ponto recebe eletroeletrônicos, mas não diz quais.

**Bairro.** Compara com os bairros dos pontos, já padronizados ("MANAIRA", "Manaíra" e "MANGABEIRA I" viram "Manaíra" e "Mangabeira"). Quando o texto bate exatamente com um bairro, só ele entra: "tambau" traz Tambaú, não Tambauzinho. Se o bairro não tem nenhum ponto cadastrado ("Bancários", "Altiplano"), ele é localizado no mapa e entram os pontos a até 1,5 km.

**Endereço ou referência.** Compara com rua, número, bairro, CEP e nome do ponto, expandindo abreviações ("Av.", "Pres.", "Jd."). Números e palavras como "rua" e "avenida" não eliminam ninguém, só ajudam a ordenar: "rua epitacio 2346" acha "Av. Presidente Epitácio Pessoa, 2346" em primeiro lugar. Se o endereço não aparece em nenhum ponto, ele é localizado (veja a seção abaixo) e entram os pontos a até 1 km.

Nos três casos há tolerância a acentos, maiúsculas e erros de digitação. A comparação usa distância de edição com transposição, então "bateira" vira "bateria" e não "batedeira". Abaixo dos campos, a tela mostra o que foi entendido de cada um.

## Como um endereço digitado é localizado

Vale para o campo "Endereço ou referência" e para o endereço de partida da rota. A busca tenta três fontes, nesta ordem:

1. **Índice de endereços do IBGE** (`data/enderecos.sqlite`). Vem do CNEFE do Censo 2022, que tem a coordenada de cada endereço do município. O `prepare` agrupa os endereços por face de quadra (o lado de um quarteirão entre duas esquinas) e guarda, para cada trecho, a faixa de números e a coordenada mediana. São cerca de 40 mil trechos de João Pessoa, Cabedelo, Bayeux, Santa Rita e Conde, em 2,8 MB. A busca roda sem rede, em poucos milissegundos.
2. **Nominatim** (OpenStreetMap): pontos de referência ("Manaíra Shopping", "UFPB"), bairros e ruas abertas depois do censo.
3. **Photon** (OpenStreetMap): última tentativa, aceita erros de digitação que o Nominatim recusa.

O índice do IBGE existe porque o OpenStreetMap não tem nome em muitas ruas da cidade e não guarda o número das casas. Num teste com 40 endereços reais sorteados do CNEFE, o Nominatim só achou a rua certa em 28, mesmo com o nome oficial completo. O índice acerta a rua em praticamente todos e, em 96% a 98% dos casos, cai a até 300 m do endereço, mesmo com erro de digitação ou sem o título da rua. Esse teste usa endereços do próprio CNEFE: ele mede a busca, não ruas que faltam no IBGE.

O que a busca no índice entende:

- **Títulos opcionais**: "Rui Carneiro" acha "Avenida Senador Ruy Carneiro". O IBGE guarda o título (Senador, Doutor, Comerciante...) separado do nome.
- **Grafias antigas**: Ruy/Rui, Luiz/Luís, Mello/Melo, Athayde/Ataíde.
- **"Rua" e "Avenida" trocados**: só ajudam a ordenar. Se as duas existem, as duas viram opção.
- **Iniciais que o IBGE abrevia**: "Aurélio Moreira de Albuquerque" acha "Aurelio M de Albuquerque".
- **Número da casa**: escolhe o trecho cuja faixa contém o número. Na faixa, números muito longe da mediana do trecho são descartados, porque o CNEFE às vezes registra apartamentos ("101, 102...") como número da casa.
- **Bairro e cidade** depois de vírgula restringem a busca. Se o bairro digitado não bater com o do IBGE, a busca tenta só com a rua.
- **CEP**: devolve o centro dos endereços do CEP.
- **Só o nome de um bairro** ("Bancários") fica para o Nominatim, que localiza o bairro inteiro.

Quando o texto serve para mais de um lugar (a mesma rua em bairros ou cidades diferentes), a busca usa o mais provável e o painel de rota lista os outros em "Não é esse lugar?". Na ordem, vêm primeiro os lugares que têm o número digitado, depois os de João Pessoa, depois a nota do nome. Quando o número não é encontrado, ou é um CEP, a tela avisa que a posição é aproximada.

## Rota até o ponto mais próximo

O painel ao lado do mapa usa o tipo de descarte informado e a localização da pessoa. Bairro e endereço não limitam a rota, porque o ponto mais próximo pode estar em outro bairro.

1. A localização vem do GPS do navegador (componente em `ui/geolocation.py`, que só funciona em HTTPS ou em localhost) ou de um endereço digitado, localizado como descrito acima.
2. Os 5 pontos mais próximos em linha reta que aceitam o item vão numa única consulta à matriz de distâncias do OSRM. Vence o menor percurso pelas ruas.
3. A rota completa do vencedor é desenhada no mapa, com distância e tempo para carro, a pé ou bicicleta.

Por padrão só entram pontos que **aceitam** o item. Uma chave inclui os pontos "confirmar com o local". No modal de qualquer ponto, "Rota no mapa" troca o destino para aquele ponto. Se o serviço de rotas falhar, a tela mostra a distância em linha reta e o link para o Google Maps.

## Mapa e detalhes

O mapa tem visual de GPS: mapa de ruas da CARTO (estilo Voyager), o município de João Pessoa pintado de azul com 20% de opacidade (`city_fill_opacity` no `config.toml`), a rota com contorno branco e a pessoa como um ponto com halo. Os marcadores têm tamanho em pixels, com teto de 24 px, então continuam do mesmo tamanho em qualquer zoom. Se o arquivo do limite faltar, o mapa abre normalmente, só sem o azul.

Pontos a menos de 60 m uns dos outros viram um marcador só, com o número de pontos. Isso cobre, por exemplo, três programas de coleta dentro do mesmo supermercado. Clicar num marcador ou numa linha da tabela abre um modal com o que o ponto recebe, endereço, observações, contatos, a confiabilidade da coordenada e links para o Google Maps. Quando o marcador junta vários pontos, cada um ganha uma aba.

Os bairros e endereços completados pelo OpenStreetMap aparecem no modal com o aviso "aproximado".

## Configuração

Tudo fica em `config.toml`, nesta pasta: caminhos dos dados, User-Agent, URLs do Nominatim, do Photon, do OSRM e do IBGE, cidades do índice de endereços (`[addresses.cities]`, cidade = arquivo do CNEFE), quantas opções mostrar para um endereço ambíguo, área de busca, raios de proximidade, meios de transporte, opacidade do município no mapa e textos da tela. Para acrescentar uma cidade ao índice, inclua o arquivo dela em `[addresses.cities]` e rode `prepare --so enderecos`. Os arquivos de cada município estão no [servidor do IBGE](https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/).

Os serviços usados são os públicos do OpenStreetMap: [Nominatim](https://operations.osmfoundation.org/policies/nominatim/), [Photon](https://photon.komoot.io) e o OSRM do [FOSSGIS](https://routing.openstreetmap.de/about.html). Eles servem para uso moderado. Para publicar o app com muito acesso, aponte `base_url`/`photon_url` para instâncias próprias.

## Arquitetura

```
src/pages/pontos_descarte/
├── page.py              a tela: só junta os componentes de ui/
├── prepare.py           CLI: planilha → data/pontos_descarte.json; IBGE → data/limite_joao_pessoa.geojson e data/enderecos.sqlite
├── bootstrap.py         composition root (pontos, índice de endereços, clients e services)
├── config.toml          configurações da página
├── config.py            config.toml → Settings
├── data/                planilha original, JSON dos pontos, limite do município e índice de endereços
├── domain/              modelos, normalização de texto, vocabulário de descarte, bairros, índice de endereços, geometria
├── clients/             sessão HTTP com retry, Nominatim e Photon (geocodificação), OSRM (rotas), IBGE (limite e CNEFE)
├── repositories/        leitura dos pontos, do limite do município e do índice de endereços (SQLite)
├── services/            busca pelos três filtros, localização de endereços em camadas e rota até o mais próximo
├── etl/                 limpeza da planilha, enriquecimento pelo OpenStreetMap e CNEFE → trechos de rua
└── ui/                  filtros, mapa, modal, painel de rota, tabela, GPS e cache
```
