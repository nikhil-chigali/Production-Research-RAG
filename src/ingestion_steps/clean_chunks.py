import json
import re
from pathlib import Path

from prefect import task, get_run_logger

from src.utils.ingest_config import get_config

_ARXIV_STAMP_RE = re.compile(
    r"(\d\s+){3,}[a-zA-Z]\s+[a-zA-Z]\s+[a-zA-Z]"
    r".*?v\s*i\s*X\s*r\s*a",
    re.DOTALL,
)

_INLINE_PAGE_NUM_RE = re.compile(r"\n\n\d{1,2}\n\n")
_TRAILING_PAGE_NUM_RE = re.compile(r"\n\n\d{1,2}\s*$")

_EQUATION_NUM_RE = re.compile(r"\n\n\(\d+\)\n\n")


def _normalize_ligatures(text: str) -> str:
    """Replace common OCR ligature characters with their ASCII equivalents."""
    return text.replace("\ufb01", "fi").replace("\ufb02", "fl")


def _strip_arxiv_stamps(text: str) -> str:
    """Remove garbled reversed arXiv watermark text produced by OCR."""
    return _ARXIV_STAMP_RE.sub("", text)


def _strip_inline_page_numbers(text: str) -> str:
    """Remove bare page numbers that appear on their own line."""
    text = _INLINE_PAGE_NUM_RE.sub("\n\n", text)
    text = _TRAILING_PAGE_NUM_RE.sub("", text)
    return text


def _strip_equation_numbers(text: str) -> str:
    """Remove standalone equation number markers like (1), (2)."""
    return _EQUATION_NUM_RE.sub("\n\n", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse 3+ consecutive newlines to 2 and strip edges."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_text(text: str) -> str:
    """Chain all text-level cleaning functions in order."""
    text = _normalize_ligatures(text)
    text = _strip_arxiv_stamps(text)
    text = _strip_inline_page_numbers(text)
    text = _strip_equation_numbers(text)
    text = _normalize_whitespace(text)
    return text


def _extract_original(text: str) -> str:
    """Return the 'Original:' portion of a chunk's text, if present."""
    marker = "; Original: "
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[idx + len(marker) :]


def _is_reference_chunk(text: str) -> bool:
    """Detect bibliography / reference-list chunks."""
    original = _extract_original(text).strip()
    lower = original.lower()

    if lower.startswith("references"):
        return True

    prefix = text[: text.find("; Original: ")] if "; Original: " in text else ""
    if any(kw in prefix.lower() for kw in ("references", "bibliography")):
        return True

    numbered_refs = re.findall(r"\[\d+\]", original)
    if len(numbered_refs) >= 4:
        return True

    return False


def _is_garbled_figure_chunk(text: str) -> bool:
    """Detect chunks that are mostly garbled OCR of figures or attention maps."""
    if "<EOS>" in text or "<pad>" in text:
        return True

    words = text.split()
    if len(words) < 10:
        return False

    repeated = sum(1 for a, b in zip(words, words[1:]) if a == b)
    if repeated / len(words) > 0.3:
        return True

    return False


@task(name="clean_chunks", log_prints=True)
def clean_chunks(parsed_paths: list[Path], output_dir: Path) -> list[Path]:
    """Clean chunked JSON files: fix text noise, drop low-value chunks.

    Reads each JSON produced by parse_and_chunk, applies text-level fixes
    (ligatures, arXiv stamps, page numbers, equation numbers, whitespace),
    then drops reference, garbled-figure, and too-short chunks. Writes
    cleaned JSON to output_dir and returns the new file paths.
    """
    logger = get_run_logger()
    cfg = get_config()
    min_len = cfg.get("cleaning", {}).get("min_chunk_length", 50)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []

    for path in parsed_paths:
        with open(path) as f:
            chunks: list[dict] = json.load(f)

        original_count = len(chunks)
        cleaned: list[dict] = []

        for chunk in chunks:
            text = chunk.get("text", "")
            text = _clean_text(text)

            if _is_reference_chunk(text):
                continue
            if _is_garbled_figure_chunk(text):
                continue

            original_portion = _extract_original(text)
            if len(original_portion.strip()) < min_len:
                continue

            chunk["text"] = text
            cleaned.append(chunk)

        dropped = original_count - len(cleaned)
        logger.info(
            f"{path.name}: {original_count} → {len(cleaned)} chunks "
            f"({dropped} dropped)"
        )

        out_path = output_dir / path.name
        with open(out_path, "w") as f:
            json.dump(cleaned, f, indent=4)

        output_paths.append(out_path)

    logger.info(f"Cleaning complete: {len(output_paths)} file(s) written to {output_dir}")
    return output_paths
