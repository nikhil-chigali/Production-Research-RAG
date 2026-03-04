from pathlib import Path

from dotenv import load_dotenv
from prefect import flow, task, get_run_logger

from src.ingestion_steps import parse_and_chunk

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent.resolve()


# ---------------------------------------------------------------------------
# Placeholder tasks (to be implemented)
# ---------------------------------------------------------------------------

@task(name="clean_chunks", log_prints=True)
def clean_chunks(parsed_paths: list[Path]) -> list[Path]:
    """Remove noisy elements from chunked JSON files.

    TODO:
    - Strip arXiv ID garble, inline page numbers
    - Drop reference-only and attention-visualization chunks
    - Drop chunks below a minimum token threshold
    """
    logger = get_run_logger()
    logger.warning("clean_chunks is a placeholder — passing through unchanged")
    return parsed_paths


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


@task(name="upsert_to_pinecone", log_prints=True)
def upsert_to_pinecone(vectors: list[dict]) -> None:
    """Upsert hybrid vectors into Pinecone serverless index.

    TODO:
    - Create/connect to Pinecone index
    - Batch upsert dense + sparse vectors with metadata
    """
    logger = get_run_logger()
    logger.warning("upsert_to_pinecone is a placeholder — skipping")


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

@flow(name="ingestion-pipeline", log_prints=True)
def ingestion_pipeline(env: str = "dev") -> None:
    """End-to-end ingestion pipeline for research paper PDFs.

    Orchestrates: parse & chunk -> clean -> create documents -> embed -> upsert.
    """
    logger = get_run_logger()
    logger.info(f"Starting ingestion pipeline (env={env})")

    data_dir = ROOT_DIR / "data" / env
    input_dir = data_dir / "pdfs"
    output_dir = data_dir / "parsed"

    parsed_paths = parse_and_chunk(input_dir=input_dir, output_dir=output_dir)
    cleaned_paths = clean_chunks(parsed_paths)
    documents = create_documents(cleaned_paths)
    vectors = embed(documents)
    upsert_to_pinecone(vectors)

    logger.info("Ingestion pipeline complete")
