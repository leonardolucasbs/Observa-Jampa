from collections.abc import Callable, Sequence

import streamlit as st


def render_period_heading(title: Callable[[int], str], options: Sequence[int], key: str) -> int:
    """Título da seção com o filtro de período na mesma linha; devolve o número de dias escolhido."""
    default = options[-1]
    # O Streamlit já atualiza o estado do widget antes de rodar o script de novo,
    # então dá para montar o título com o valor escolhido antes de desenhar o filtro ao lado dele.
    selected = st.session_state.get(key, default)
    with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
        st.subheader(title(selected), width="content")
        days = st.segmented_control(
            "Período",
            options=list(options),
            default=default,
            required=True,
            format_func=lambda value: f"{value} dias",
            key=key,
            label_visibility="collapsed",
        )
    return int(days)
