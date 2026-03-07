from prefect import task, get_run_logger


@task(name="embed", log_prints=True)
def embed(documents: list[dict]) -> list[dict]:
    """Generate dense + sparse embeddings for each document.

    TODO:
    - Dense: OpenAI text-embedding-3-small (1536-dim)
    - Sparse: pinecone-text BM25Encoder
    """
    logger = get_run_logger()
    logger.warning("embed is a placeholder — returning empty list")
    return []
