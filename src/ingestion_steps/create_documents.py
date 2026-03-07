import json
import re
from pathlib import Path

from langchain_core.documents import Document
from prefect import task, get_run_logger

_SEPARATOR = "; Original: "

_QUOTED_TITLE_RE = re.compile(r'"([^"]+)"')

_SECTION_HEADING_RE = re.compile(r"^\d+(\.\d+)*\s+.+")


def _split_prefix_original(text: str) -> tuple[str, str]:
    """Split chunk text into (prefix, original) on the '; Original: ' marker."""
    idx = text.find(_SEPARATOR)
    if idx == -1:
        return "", text

    prefix = text[:idx]
    if prefix.startswith("Prefix: "):
        prefix = prefix[len("Prefix: "):]

    original = text[idx + len(_SEPARATOR):]
    return prefix, original


def _extract_paper_title(prefix: str, fallback_filename: str) -> str:
    """Extract the paper title from a contextual prefix string.

    Titles appear in quotes inside the prefix, e.g.:
    '...paper "Attention Is All You Need," which introduces...'
    Falls back to the filename stem if no quoted title is found.
    """
    match = _QUOTED_TITLE_RE.search(prefix)
    if match:
        return match.group(1).rstrip(",.")
    return Path(fallback_filename).stem


def _extract_section(original: str) -> str | None:
    """Return the section heading if the original text starts with one."""
    first_line = original.strip().split("\n", 1)[0].strip()
    if not first_line:
        return None

    if _SECTION_HEADING_RE.match(first_line):
        return first_line

    if len(first_line) < 80 and not first_line.endswith("."):
        return first_line

    return None


@task(name="create_documents", log_prints=True)
def create_documents(cleaned_paths: list[Path]) -> list[Document]:
    """Convert cleaned JSON chunks into LangChain Document objects.

    Reads each cleaned JSON file, splits the 'Prefix: ...; Original: ...'
    text format, extracts structured metadata (paper title, section, page
    number, etc.), and returns a flat list of Document objects.
    """
    logger = get_run_logger()
    all_docs: list[Document] = []

    for path in cleaned_paths:
        with open(path) as f:
            chunks: list[dict] = json.load(f)

        for idx, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {})

            prefix, original = _split_prefix_original(text)
            filename = meta.get("filename", path.name)

            doc = Document(
                page_content=original,
                metadata={
                    "context_prefix": prefix,
                    "paper_title": _extract_paper_title(prefix, filename),
                    "section": _extract_section(original),
                    "page_number": meta.get("page_number"),
                    "source_filename": filename,
                    "has_table": "text_as_html" in meta,
                    "chunk_index": idx,
                    "element_id": chunk.get("element_id", ""),
                },
            )
            all_docs.append(doc)

        logger.info(f"{path.name}: created {len(chunks)} Document(s)")

    logger.info(f"Total: {len(all_docs)} Document(s) from {len(cleaned_paths)} file(s)")
    return all_docs
