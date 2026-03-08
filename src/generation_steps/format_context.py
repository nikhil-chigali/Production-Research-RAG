from langchain_core.documents import Document
from prefect import task, get_run_logger


@task(name="format_context", log_prints=True)
def format_context(documents: list[Document]) -> str:
    """Format retrieved documents into a numbered source string for the LLM.

    Each document becomes a ``[Source N]`` block with paper title, section,
    page number, and the full chunk text.  The concatenated string is ready
    to be injected into a generation prompt.
    """
    logger = get_run_logger()

    if not documents:
        logger.warning("No documents to format")
        return ""

    blocks: list[str] = []
    for i, doc in enumerate(documents, start=1):
        meta = doc.metadata
        paper = meta.get("paper_title", "Unknown")
        section = meta.get("section", "—")
        page = meta.get("page_number", "—")

        block = (
            f"[Source {i}]\n"
            f"Paper: {paper}\n"
            f"Section: {section}\n"
            f"Page: {page}\n"
            f"\n"
            f"{doc.page_content}"
        )
        blocks.append(block)

    context = "\n\n".join(blocks)
    logger.info(f"Formatted {len(blocks)} source(s) into context ({len(context)} chars)")
    return context
