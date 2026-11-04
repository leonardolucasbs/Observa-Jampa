"""Página inicial do ObservaJP. A landing page ainda será desenvolvida; por ora só apresenta as páginas."""

import streamlit as st

st.title("ObservaJP")
st.subheader("Observatório Ambiental de João Pessoa", anchor=False)
st.info("A página inicial está em construção. Enquanto isso, escolha um tema na barra de cima.", icon=":material/construction:")

poluentes_col, descarte_col = st.columns(2)
with poluentes_col.container(border=True):
    st.markdown("#### 🌫️ Poluentes")
    st.write("Qualidade do ar em João Pessoa, histórico e comparação com outras capitais.")
    st.page_link("pages/poluentes/page.py", label="Ver qualidade do ar", icon=":material/arrow_forward:")
with descarte_col.container(border=True):
    st.markdown("#### ♻️ Pontos de descarte")
    st.write("Onde descartar eletroeletrônicos, com busca por item, bairro e rota até o ponto mais próximo.")
    st.page_link("pages/pontos_descarte/page.py", label="Encontrar um ponto", icon=":material/arrow_forward:")
