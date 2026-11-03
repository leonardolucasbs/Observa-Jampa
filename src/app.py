"""Ponto de entrada do ObservaJP: configura a navegação entre as páginas.

Arquitetura baseada em recursos: cada página é uma pasta em `pages/<tema>/` com o `page.py`
e todo o código de que ela precisa. Para adicionar uma página, registre um `st.Page` em `PAGES`
(passo a passo no README da raiz).
"""

import streamlit as st

st.set_page_config(page_title="ObservaJP", layout="wide")

PAGES = {
    "Meio ambiente": [
        st.Page("pages/poluentes/page.py", title="Poluentes", icon="🌫️", url_path="poluentes", default=True),
    ],
}

st.navigation(PAGES).run()
