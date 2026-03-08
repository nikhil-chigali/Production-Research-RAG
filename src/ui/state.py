"""Processing state tracker for the ingestion pipeline.

Maintains a JSON state file at ``data/{env}/.processing_state.json`` that
records which PDFs have been fully ingested (parsed, cleaned, embedded,
and upserted to Pinecone).

For files ingested via the CLI before the Streamlit app existed, the
``reconcile`` function detects them by fuzzy-matching PDF filenames
against cleaned JSON filenames in ``data/{env}/cleaned/``.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent.resolve()

_STATE_FILENAME = ".processing_state.json"


def _normalize(name: str) -> str:
    """Lowercase and strip all non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _state_path(env: str) -> Path:
    return ROOT_DIR / "data" / env / _STATE_FILENAME


def _read_state(env: str) -> dict:
    path = _state_path(env)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _write_state(env: str, state: dict) -> None:
    path = _state_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def reconcile(env: str) -> dict:
    """Auto-detect previously processed PDFs by matching against cleaned JSONs.

    Normalizes both PDF stems and cleaned JSON stems (lowercase, strip
    non-alphanumeric), then checks whether the normalized PDF stem is a
    prefix of any normalized cleaned JSON stem. New matches are persisted
    to the state file.
    """
    state = _read_state(env)

    pdf_dir = ROOT_DIR / "data" / env / "pdfs"
    cleaned_dir = ROOT_DIR / "data" / env / "cleaned"

    if not pdf_dir.exists() or not cleaned_dir.exists():
        return state

    cleaned_norms = [_normalize(p.stem) for p in cleaned_dir.glob("*.json")]
    if not cleaned_norms:
        return state

    updated = False
    for pdf in pdf_dir.glob("*.pdf"):
        if pdf.name in state:
            continue
        norm_pdf = _normalize(pdf.stem)
        if any(cn.startswith(norm_pdf) for cn in cleaned_norms):
            state[pdf.name] = {
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "detected": True,
            }
            updated = True

    if updated:
        _write_state(env, state)

    return state


def get_file_statuses(env: str) -> dict[str, bool]:
    """Return ``{pdf_name: is_processed}`` for every PDF in the env folder."""
    state = reconcile(env)

    pdf_dir = ROOT_DIR / "data" / env / "pdfs"
    if not pdf_dir.exists():
        return {}

    return {
        pdf.name: pdf.name in state
        for pdf in sorted(pdf_dir.glob("*.pdf"))
    }


def mark_as_processed(env: str, filenames: list[str]) -> None:
    """Record *filenames* as successfully processed."""
    state = _read_state(env)
    now = datetime.now(timezone.utc).isoformat()
    for name in filenames:
        state[name] = {"processed_at": now}
    _write_state(env, state)
