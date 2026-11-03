import streamlit as st


def render_model_disclaimer(disclaimer: str) -> None:
    st.warning(disclaimer, icon="⚠️")


def render_footer(attribution: str) -> None:
    st.divider()
    st.caption(attribution)
