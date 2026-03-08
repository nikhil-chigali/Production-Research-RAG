"""HybridRAG-Bench — Streamlit application.

Launch with:
    streamlit run app.py
"""

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from src.ui import file_manager, chat

st.set_page_config(
    page_title="HybridRAG-Bench",
    page_icon="📚",
    layout="wide",
)

# --- sidebar ---
with st.sidebar:
    st.title("HybridRAG-Bench")
    st.caption("Enterprise RAG for research papers")

    st.divider()

    env = st.radio(
        "Environment",
        options=["dev", "prod"],
        horizontal=True,
        key="env",
    )

    st.divider()
    st.markdown(
        "**Stack:** Unstructured · OpenAI · Pinecone · LangChain · Prefect"
    )

# --- main content ---
tab_files, tab_chat = st.tabs(["Files", "Chat"])

with tab_files:
    file_manager.render(env)

with tab_chat:
    chat.render(env)
