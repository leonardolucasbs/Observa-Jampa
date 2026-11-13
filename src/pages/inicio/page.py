from pathlib import Path

import streamlit as st

TREE_URL = "https://www.cear.ufpb.br/tree/descarte-seus-residuos/"
LOGO = Path(__file__).resolve().parents[3] / "img" / "percursor-analysis.png"

st.html(
    """
    <style>
      .st-key-hero {
        background: linear-gradient(135deg, #1D4899 0%, #021047 100%);
        border-radius: 20px;
        padding: 2.4rem 2.6rem 2.2rem;
      }
      .st-key-hero h1, .st-key-hero p { color: #FFFFFF; }
      .st-key-hero_logo img { max-width: 46rem; margin-top: 1.5rem; border-radius: 12px; }
      [class*="st-key-feature_"] { border-top: 6px solid #1D4899; }
      [class*="st-key-feature_"] > div:last-child { margin-top: auto; }
      [class*="st-key-feature_"] [data-testid="stPageLink-NavLink"] {
        background: #1D4899;
        border-radius: 10px;
        padding: 0.55rem 1rem;
      }
      [class*="st-key-feature_"] [data-testid="stPageLink-NavLink"]:hover { background: #021047; }
      [class*="st-key-feature_"] [data-testid="stPageLink-NavLink"] p,
      [class*="st-key-feature_"] [data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] {
        color: #FFFFFF;
        font-weight: 600;
      }
      .st-key-tree_credit {
        background: #F0F4FF;
        border-radius: 12px;
        padding: 0.8rem 1rem;
      }
    </style>
    """
)

with st.container(key="hero"):

    col1, col2 = st.columns([1, 1], gap="medium")
    with col1:

        st.html(
            '<div style="color:#FFFFFF;opacity:.85;font-size:.85rem;font-weight:700;letter-spacing:.12em;'
            'text-transform:uppercase;">Observatório Ambiental de João Pessoa</div>'
        )
        st.title("Observa Jampa", anchor=False)
        st.html(
            '<p style="color:#FFFFFF;font-size:1.2rem;line-height:1.5;max-width:46rem;margin:0;">'
            "Dados ambientais da cidade reunidos num só lugar e explicados em linguagem simples: "
            "a qualidade do ar que você respira, onde descartar eletroeletrônicos e a previsão de chuva "
            "com os avisos meteorológicos oficiais.</p>"
        )
    with col2:
        if LOGO.exists():
            with st.container(key="hero_logo"):
                st.image(str(LOGO), width=1060)

st.write("")
st.subheader("O que você encontra aqui", anchor=False)

poluentes_col, descarte_col, chuvas_col = st.columns(3, gap="medium")

with poluentes_col, st.container(border=True, height="stretch", key="feature_poluentes"):
    st.markdown("### 🌫️ Qualidade do ar")
    st.markdown("**O ar está bom para sair hoje?**")
    st.markdown(
        "- Situação do ar agora\n"
        "- Como o ar esteve nos últimos dias\n"
    )
    st.caption("Dados: Open-Meteo e CAMS (Copernicus). São estimativas de modelo, não medições de sensores.")
    st.page_link("pages/poluentes/page.py", label="Ver a qualidade do ar", icon=":material/arrow_forward:")

with descarte_col, st.container(border=True, height="stretch", key="feature_descarte"):
    st.markdown("### ♻️ Pontos de descarte")
    st.markdown("**Onde entrego pilhas, celulares ou eletrodomésticos?**")
    st.markdown(
        "- Mapa dos pontos de entrega de eletroeletrônicos\n"
        "- Busca pelo que você quer descartar, por bairro ou endereço\n"
        "- Rota até o ponto mais próximo"
    )
    with st.container(key="tree_credit"):
        st.markdown(
            "**Mérito:** os pontos de entrega voluntária de João Pessoa e região são mapeados pelo projeto "
            "de extensão **TREE — Tratamento de Resíduos Eletroeletrônicos**, da UFPB.  \n"
            f"[Conheça o trabalho do TREE e as orientações de descarte]({TREE_URL})"
        )
    st.page_link("pages/pontos_descarte/page.py", label="Encontrar um ponto", icon=":material/arrow_forward:")

with chuvas_col, st.container(border=True, height="stretch", key="feature_chuvas"):
    st.markdown("### 🌧️ Chuvas e alertas")
    st.markdown("**Vai chover? Existe algum aviso oficial?**")
    st.markdown(
        "- Chuva prevista para hoje, amanhã e os próximos 7 dias\n"
        "- Avisos meteorológicos do INMET vigentes e futuros\n"
        "- Atualização automática, com a hora de cada consulta"
    )
    st.caption("Dados: Open-Meteo (previsão) e INMET (avisos). Previsão não é chuva medida nem indica alagamento.")
    st.page_link("pages/chuvas/page.py", label="Ver a previsão e os avisos", icon=":material/arrow_forward:")

st.write("")
st.subheader("Como tratamos os dados", anchor=False)
sources_col, time_col, estimate_col = st.columns(3, gap="medium")
with sources_col:
    st.markdown(
        ":material/verified: **Fontes públicas e citadas**  \n"
        "Cada página informa de onde vêm os dados: Open-Meteo, CAMS, INMET, IBGE, OpenStreetMap e o "
        "mapeamento do projeto TREE/UFPB."
    )
with time_col:
    st.markdown(
        ":material/schedule: **Data e hora à vista**  \n"
        "As telas mostram quando os dados foram consultados e a que período se referem, para nada "
        "antigo parecer recente."
    )
with estimate_col:
    st.markdown(
        ":material/info: **Estimativa é estimativa**  \n"
        "Qualidade do ar e chuva vêm de modelos de previsão, não de sensores no seu bairro. "
    )

st.divider()
st.caption(
    "O ObservaJP é desenvolvido pela Percursor Analisys, iniciativa extensionista do Unipê. "
    "Código aberto sob a licença MIT."
)
