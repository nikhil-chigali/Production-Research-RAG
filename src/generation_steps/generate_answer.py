from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from prefect import task, get_run_logger

from src.prompts import QA_PROMPT
from src.utils.ingest_config import get_config


def _extract_sources(documents: list[Document]) -> list[dict]:
    """Build a compact source list from retrieved documents."""
    sources: list[dict] = []
    for i, doc in enumerate(documents, start=1):
        meta = doc.metadata
        sources.append(
            {
                "source_number": i,
                "paper_title": meta.get("paper_title", "Unknown"),
                "section": meta.get("section"),
                "page_number": meta.get("page_number"),
                "snippet": doc.page_content[:200],
            }
        )
    return sources


@task(name="generate_answer", log_prints=True)
def generate_answer(
    query: str,
    context: str,
    documents: list[Document],
) -> dict:
    """Generate an answer from retrieved context using an LLM.

    Invokes the QA prompt with the formatted context and user query,
    then returns the answer alongside structured source metadata.
    """
    logger = get_run_logger()
    cfg = get_config()

    llm = ChatOpenAI(
        model=cfg.generation.model,
        temperature=cfg.generation.temperature,
        max_tokens=cfg.generation.max_tokens,
    )

    chain = QA_PROMPT | llm
    response = chain.invoke({"context": context, "query": query})

    answer = response.content
    sources = _extract_sources(documents)

    token_usage = response.usage_metadata
    if token_usage:
        logger.info(
            f"Token usage — input: {token_usage.get('input_tokens', '?')}, "
            f"output: {token_usage.get('output_tokens', '?')}"
        )

    logger.info(f"Generated answer ({len(answer)} chars) with {len(sources)} source(s)")
    return {"answer": answer, "sources": sources}
