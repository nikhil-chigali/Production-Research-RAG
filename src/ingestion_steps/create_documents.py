from pathlib import Path

from prefect import task, get_run_logger


@task(name="create_documents", log_prints=True)
def create_documents(cleaned_paths: list[Path]) -> list[dict]:
    """Convert cleaned chunks into LangChain Document objects.

    TODO:
    - Split contextual prefix into metadata
    - Extract section headings, paper title, page number
    - Build Document(page_content=..., metadata=...)
    """
    logger = get_run_logger()
    logger.warning("create_documents is a placeholder — returning empty list")
    return []
