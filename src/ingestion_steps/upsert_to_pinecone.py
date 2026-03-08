import os
import time

from pinecone import Pinecone, ServerlessSpec
from prefect import task, get_run_logger

from src.utils.ingest_config import get_config


def _get_index_name(prefix: str, env: str) -> str:
    return f"{prefix}-{env}"


def _ensure_index(
    pc: Pinecone,
    index_name: str,
    dimension: int,
    metric: str,
    cloud: str,
    region: str,
) -> None:
    """Create the index if it doesn't already exist, then wait until ready."""
    existing = [idx.name for idx in pc.list_indexes()]

    if index_name in existing:
        return

    pc.create_index(
        name=index_name,
        dimension=dimension,
        metric=metric,
        spec=ServerlessSpec(cloud=cloud, region=region),
    )

    while not pc.describe_index(index_name).status.ready:
        time.sleep(1)


def _batch_upsert(index, vectors: list[dict], batch_size: int) -> int:
    """Upsert vectors in batches, returning total upserted count."""
    upserted = 0
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch)
        upserted += len(batch)
    return upserted


@task(name="upsert_to_pinecone", log_prints=True)
def upsert_to_pinecone(vectors: list[dict], env: str = "dev") -> None:
    """Upsert hybrid vectors into a Pinecone serverless index.

    Creates the index ``arxiv-research-rag-{env}`` if it doesn't exist,
    then batch-upserts all vector records (dense + sparse + metadata).
    """
    logger = get_run_logger()

    if not vectors:
        logger.warning("No vectors to upsert")
        return

    cfg = get_config()
    pc_cfg = cfg.pinecone
    emb_cfg = cfg.embedding

    index_name = _get_index_name(pc_cfg.index_name_prefix, env)
    logger.info(f"Target index: {index_name}")

    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

    _ensure_index(
        pc,
        index_name=index_name,
        dimension=emb_cfg.dimensions,
        metric=pc_cfg.metric,
        cloud=pc_cfg.cloud,
        region=pc_cfg.region,
    )
    logger.info(f"Index '{index_name}' is ready")

    index = pc.Index(index_name)

    upserted = _batch_upsert(index, vectors, pc_cfg.upsert_batch_size)
    logger.info(f"Upserted {upserted} vectors into '{index_name}'")

    stats = index.describe_index_stats()
    logger.info(f"Index stats: {stats.total_vector_count} total vectors")
