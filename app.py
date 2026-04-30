#!/usr/bin/env python3
"""
app.py — Interface web para o gerador de carrosséis.
Rodar: streamlit run app.py
"""

import io
import os
import zipfile

import streamlit as st

from generate_carousel import gerar_conteudo_slides, criar_imagem_slide

# ──────────────────────────────────────────────────────────────────────────────
# Configuração da página
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Gerador de Carrossel",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Esconde elementos nativos do Streamlit que ficam em inglês
st.markdown(
    """
    <style>
        /* Remove barra de ferramentas superior (Deploy, menu ⋮) */
        header[data-testid="stHeader"] { display: none !important; }
        /* Remove rodapé "Made with Streamlit" */
        footer { display: none !important; }
        /* Remove botão de gerenciar app no canto inferior direito */
        #MainMenu { display: none !important; }
        [data-testid="manage-app-button"] { display: none !important; }

        .block-container { padding-top: 2rem; }
        .slide-caption {
            text-align: center;
            font-size: 0.8rem;
            color: #888;
            margin-top: 4px;
        }
        div[data-testid="stImage"] img {
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        .stButton > button {
            width: 100%;
            border-radius: 10px;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar — inputs do usuário
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🎨 Gerador de Carrossel")
    st.caption("Crie slides prontos para Instagram e LinkedIn em segundos.")
    st.divider()

    tema = st.text_area(
        "Tema do carrossel",
        placeholder='Ex: "5 hábitos de pessoas produtivas"',
        height=100,
    )

    num_slides = st.slider(
        "Número de slides",
        min_value=3,
        max_value=12,
        value=5,
        step=1,
    )

    st.divider()
    gerar = st.button("✨ Gerar Carrossel", type="primary", disabled=not tema.strip())

    st.caption("Os slides são gerados localmente, sem enviar dados para nenhum servidor.")

# ──────────────────────────────────────────────────────────────────────────────
# Área principal
# ──────────────────────────────────────────────────────────────────────────────

st.title("Prévia dos Slides")

if not gerar:
    st.info("Preencha o tema na barra lateral e clique em **Gerar Carrossel** para começar.", icon="👈")
    st.stop()

# Geração
with st.spinner(f"Gerando {num_slides} slides sobre "{tema}"…"):
    slides_data = gerar_conteudo_slides(tema, num_slides)

    # Renderiza cada slide em memória (sem salvar em disco)
    imagens_bytes: list[tuple[str, bytes]] = []
    for i, slide in enumerate(slides_data, start=1):
        import tempfile, os as _os
        with tempfile.TemporaryDirectory() as tmp:
            caminho = criar_imagem_slide(slide, i, len(slides_data), tmp)
            with open(caminho, "rb") as f:
                imagens_bytes.append((f"slide_{i:02d}.png", f.read()))

# ── Exibe slides em grade ─────────────────────────────────────────────────────
COLUNAS = 3
cols_grade = st.columns(COLUNAS)

for idx, (nome, dados) in enumerate(imagens_bytes):
    col = cols_grade[idx % COLUNAS]
    with col:
        st.image(dados, use_container_width=True)
        titulo = slides_data[idx]["titulo"]
        st.markdown(
            f'<p class="slide-caption"><b>{idx+1}/{len(imagens_bytes)}</b> — {titulo}</p>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label=f"⬇ Baixar slide {idx+1}",
            data=dados,
            file_name=nome,
            mime="image/png",
            key=f"dl_{idx}",
        )

st.divider()

# ── Botão para baixar todos em ZIP ───────────────────────────────────────────
buf_zip = io.BytesIO()
with zipfile.ZipFile(buf_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for nome, dados in imagens_bytes:
        zf.writestr(nome, dados)
buf_zip.seek(0)

tema_slug = tema.strip().lower().replace(" ", "_")[:40]
st.download_button(
    label="📦 Baixar todos os slides (.zip)",
    data=buf_zip,
    file_name=f"carrossel_{tema_slug}.zip",
    mime="application/zip",
    type="primary",
)
