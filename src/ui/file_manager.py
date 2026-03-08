"""Tab 1 — File Manager: view PDFs, upload new ones, trigger ingestion."""

from pathlib import Path

import streamlit as st

from src.ingestion_flow import ingestion_pipeline
from src.ui.state import get_file_statuses, mark_as_processed, ROOT_DIR


def _pdf_dir(env: str) -> Path:
    return ROOT_DIR / "data" / env / "pdfs"


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _handle_uploads(env: str) -> None:
    """File uploader that saves PDFs to ``data/{env}/pdfs/``."""
    uploaded = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"uploader_{env}",
    )
    if not uploaded:
        return

    dest = _pdf_dir(env)
    dest.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    for f in uploaded:
        target = dest / f.name
        if not target.exists():
            target.write_bytes(f.getvalue())
            saved.append(f.name)

    if saved:
        st.success(f"Saved {len(saved)} file(s): {', '.join(saved)}")
        st.rerun()


def _run_ingestion(env: str, selected: list[str]) -> None:
    """Run the ingestion pipeline on *selected* PDFs and update state."""
    with st.status("Running ingestion pipeline...", expanded=True) as status:
        try:
            st.write(f"Processing {len(selected)} file(s): {', '.join(selected)}")
            ingestion_pipeline(file_names=selected, env=env)
            mark_as_processed(env, selected)
            status.update(label="Ingestion complete!", state="complete")
            st.rerun()
        except Exception as exc:
            status.update(label="Ingestion failed", state="error")
            st.error(f"Pipeline error: {exc}")


def render(env: str) -> None:
    """Render the File Manager tab."""
    _handle_uploads(env)

    st.divider()

    statuses = get_file_statuses(env)

    if not statuses:
        st.info(
            f"No PDF files found in `data/{env}/pdfs/`. "
            "Upload files above to get started."
        )
        return

    # --- file table with checkboxes ---
    selected: list[str] = []

    for filename, processed in statuses.items():
        filepath = _pdf_dir(env) / filename
        size = _format_size(filepath.stat().st_size) if filepath.exists() else "—"

        col_check, col_name, col_size, col_status = st.columns([0.5, 4, 1.5, 2])

        with col_check:
            checked = st.checkbox(
                "select",
                key=f"chk_{env}_{filename}",
                label_visibility="collapsed",
                disabled=processed,
            )
        with col_name:
            st.markdown(f"**{filename}**")
        with col_size:
            st.caption(size)
        with col_status:
            if processed:
                st.markdown(":green[Processed]")
            else:
                st.markdown(":gray[Not Processed]")

        if checked and not processed:
            selected.append(filename)

    # --- action bar ---
    st.divider()

    col_btn, col_info = st.columns([2, 4])
    with col_btn:
        run_disabled = len(selected) == 0
        if st.button(
            f"Process Selected ({len(selected)})",
            disabled=run_disabled,
            type="primary",
            use_container_width=True,
        ):
            _run_ingestion(env, selected)

    with col_info:
        total = len(statuses)
        done = sum(1 for v in statuses.values() if v)
        st.caption(f"{done} / {total} files processed")
