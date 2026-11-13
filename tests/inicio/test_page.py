"""Fumaça da página inicial: apresenta as três funcionalidades, com link para cada página, e dá o crédito ao TREE/UFPB."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

# Abre pelo app.py: o st.page_link só reconhece páginas registradas no st.navigation, e a inicial é a padrão.
APP = str(Path(__file__).resolve().parents[2] / "src" / "app.py")
TREE_URL = "https://www.cear.ufpb.br/tree/descarte-seus-residuos/"


def test_landing_page_presents_the_three_features():
    app = AppTest.from_file(APP, default_timeout=30).run()

    assert not app.exception
    assert app.title[0].value == "Observa Jampa"
    headings = [block.value for block in app.markdown if block.value.startswith("### ")]
    assert headings == ["### 🌫️ Qualidade do ar", "### ♻️ Pontos de descarte", "### 🌧️ Chuvas e alertas"]
    links = {link.proto.label: link.proto.page for link in app.get("page_link")}
    assert links == {
        "Ver a qualidade do ar": "poluentes",  # url_path das páginas registradas no app.py
        "Encontrar um ponto": "pontos_descarte",
        "Ver a previsão e os avisos": "chuvas",
    }


def test_disposal_section_credits_the_tree_project():
    app = AppTest.from_file(APP, default_timeout=30).run()

    credit = next(block.value for block in app.markdown if block.value.startswith("**Mérito:**"))
    assert "TREE — Tratamento de Resíduos Eletroeletrônicos" in credit
    assert "UFPB" in credit
    assert f"]({TREE_URL})" in credit
