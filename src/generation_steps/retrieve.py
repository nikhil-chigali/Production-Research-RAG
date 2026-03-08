import os

from langchain_community.retrievers import PineconeHybridSearchRetriever
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder
from prefect import task, get_run_logger

from src.utils.ingest_config import get_config


def _build_retriever(env: str, cfg) -> PineconeHybridSearchRetriever:
    """Connect to Pinecone and build a hybrid search retriever."""
    index_name = f"{cfg.pinecone.index_name_prefix}-{env}"

    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index = pc.Index(index_name)

    embeddings = OpenAIEmbeddings(
        model=cfg.embedding.model,
        dimensions=cfg.embedding.dimensions,
    )
    bm25 = BM25Encoder.default()

    return PineconeHybridSearchRetriever(
        embeddings=embeddings,
        sparse_encoder=bm25,
        index=index,
        top_k=cfg.retrieval.top_k,
        alpha=cfg.retrieval.alpha,
        text_key="text",
    )


@task(name="retrieve", log_prints=True)
def retrieve(query: str, env: str = "dev") -> list[Document]:
    """Retrieve relevant chunks via hybrid search (dense + sparse).

    Connects to the Pinecone index ``arxiv-research-rag-{env}`` and
    runs an alpha-weighted hybrid query using OpenAI dense embeddings
    and BM25 sparse vectors.
    """
    logger = get_run_logger()
    cfg = get_config()

    index_name = f"{cfg.pinecone.index_name_prefix}-{env}"
    logger.info(
        f"Querying '{index_name}' (top_k={cfg.retrieval.top_k}, "
        f"alpha={cfg.retrieval.alpha})"
    )

    retriever = _build_retriever(env, cfg)
    documents = retriever.invoke(query)

    logger.info(f"Retrieved {len(documents)} document(s)")
    return documents
