from prefect import task, get_run_logger


@task(name="upsert_to_pinecone", log_prints=True)
def upsert_to_pinecone(vectors: list[dict]) -> None:
    """Upsert hybrid vectors into Pinecone serverless index.

    TODO:
    - Create/connect to Pinecone index
    - Batch upsert dense + sparse vectors with metadata
    """
    logger = get_run_logger()
    logger.warning("upsert_to_pinecone is a placeholder — skipping")
