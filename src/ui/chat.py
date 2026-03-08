"""Tab 2 — Chat: ask questions against the ingested paper corpus."""

import streamlit as st

from src.generation_flow import generation


def _ensure_history(env: str) -> list[dict]:
    """Return the message list for *env*, creating it if needed."""
    key = f"messages_{env}"
    if key not in st.session_state:
        st.session_state[key] = []
    return st.session_state[key]


def _display_sources(sources: list[dict]) -> None:
    """Render source citations inside an expander."""
    with st.expander(f"Sources ({len(sources)})"):
        for src in sources:
            title = src.get("paper_title", "Unknown")
            section = src.get("section") or "—"
            page = src.get("page_number") or "—"
            st.markdown(
                f"**[Source {src['source_number']}]** {title}  \n"
                f"Section: {section} · Page: {page}"
            )


def render(env: str) -> None:
    """Render the Chat tab."""
    messages = _ensure_history(env)

    if not messages:
        st.markdown(
            "_Ask a question about the papers in your knowledge base. "
            "Answers are generated from the ingested documents with source citations._"
        )

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                _display_sources(msg["sources"])

    query = st.chat_input("Ask a question about your papers...")
    if not query:
        return

    messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Searching and generating..."):
            try:
                result = generation(query=query, env=env)
                answer = result["answer"]
                sources = result["sources"]
            except Exception as exc:
                answer = f"An error occurred: {exc}"
                sources = []

        st.markdown(answer)
        if sources:
            _display_sources(sources)

    messages.append({"role": "assistant", "content": answer, "sources": sources})
