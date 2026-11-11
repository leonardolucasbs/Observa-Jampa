"""Ponto de entrada do ObservaJP: configura a navegação entre as páginas.

Arquitetura baseada em recursos: cada página é uma pasta em `pages/<tema>/` com o `page.py`
e todo o código de que ela precisa. Para adicionar uma página, registre um `st.Page` em `PAGES`
(passo a passo no README da raiz).
"""

import streamlit as st

st.set_page_config(page_title="ObservaJP", layout="wide")

# A ordem da lista é a ordem da barra de navegação no topo da tela.
PAGES = [
    st.Page("pages/inicio/page.py", title="Início", icon="🏠", url_path="inicio", default=True),
    st.Page("pages/poluentes/page.py", title="Poluentes", icon="🌫️", url_path="poluentes"),
    st.Page("pages/pontos_descarte/page.py", title="Pontos de descarte", icon="♻️", url_path="pontos_descarte"),
    st.Page("pages/chuvas/page.py", title="Chuvas e alertas", icon="🌧️", url_path="chuvas"),
]

st.navigation(PAGES, position="top").run()
