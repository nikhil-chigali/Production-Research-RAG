from langchain_core.documents import Document
from openai import OpenAI
from pinecone_text.sparse import BM25Encoder
from prefect import task, get_run_logger

from src.utils.ingest_config import get_config


def _build_embedding_texts(documents: list[Document]) -> list[str]:
    """Concatenate context prefix with original text for richer embeddings.

    The prefix carries section hierarchy and paper title from contextual
    chunking, which improves retrieval relevance when baked into the vector.
    """
    texts: list[str] = []
    for doc in documents:
        prefix = doc.metadata.get("context_prefix", "")
        if prefix:
            texts.append(f"{prefix}. {doc.page_content}")
        else:
            texts.append(doc.page_content)
    return texts


def _embed_dense(
    texts: list[str], model: str, dimensions: int, batch_size: int
) -> list[list[float]]:
    """Batch-embed texts via OpenAI embeddings API."""
    client = OpenAI()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            input=batch, model=model, dimensions=dimensions
        )
        all_embeddings.extend([item.embedding for item in response.data])

    return all_embeddings


def _embed_sparse(texts: list[str]) -> list[dict]:
    """Generate sparse BM25 vectors using MS MARCO pre-trained params."""
    bm25 = BM25Encoder.default()
    return bm25.encode_documents(texts)


def _clean_metadata(doc: Document) -> dict:
    """Build Pinecone-compatible metadata dict, dropping None values."""
    raw = {
        "text": doc.page_content,
        "context_prefix": doc.metadata.get("context_prefix", ""),
        "paper_title": doc.metadata.get("paper_title", ""),
        "section": doc.metadata.get("section"),
        "page_number": doc.metadata.get("page_number"),
        "source_filename": doc.metadata.get("source_filename", ""),
        "has_table": doc.metadata.get("has_table", False),
        "chunk_index": doc.metadata.get("chunk_index", 0),
    }
    return {k: v for k, v in raw.items() if v is not None}


@task(name="embed", log_prints=True)
def embed(documents: list[Document]) -> list[dict]:
    """Generate dense + sparse embeddings and build Pinecone vector records.

    Dense vectors come from OpenAI ``text-embedding-3-small``.  Sparse
    vectors use a pre-trained BM25 encoder (MS MARCO).  Both are computed
    over the contextually enriched text (prefix + original) so the vectors
    capture section hierarchy and paper context.

    Returns a list of dicts ready for ``upsert_to_pinecone``, each with
    keys: ``id``, ``values``, ``sparse_values``, ``metadata``.
    """
    logger = get_run_logger()

    if not documents:
        logger.warning("No documents to embed")
        return []

    cfg = get_config()
    model = cfg.embedding.model
    dimensions = cfg.embedding.dimensions
    batch_size = cfg.embedding.batch_size

    texts = _build_embedding_texts(documents)
    logger.info(f"Embedding {len(texts)} chunks (model={model}, dim={dimensions})")

    dense_vectors = _embed_dense(texts, model, dimensions, batch_size)
    logger.info(
        f"Dense: {len(dense_vectors)} vectors, {len(dense_vectors[0])}-dim"
    )

    sparse_vectors = _embed_sparse(texts)
    logger.info(f"Sparse: {len(sparse_vectors)} BM25 vectors")

    vectors: list[dict] = []
    for doc, dense, sparse in zip(documents, dense_vectors, sparse_vectors):
        element_id = doc.metadata.get("element_id", "")
        fallback_id = f"chunk-{doc.metadata.get('chunk_index', 0)}"

        vectors.append(
            {
                "id": element_id or fallback_id,
                "values": dense,
                "sparse_values": sparse,
                "metadata": _clean_metadata(doc),
            }
        )

    logger.info(f"Built {len(vectors)} vector records for upsert")
    return vectors
