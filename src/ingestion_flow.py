from pathlib import Path

from dotenv import load_dotenv
from prefect import flow, get_run_logger

from src.ingestion_steps import (
    parse_and_chunk,
    clean_chunks,
    create_documents,
    embed,
    upsert_to_pinecone,
)

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent.resolve()


@flow(name="ingestion-pipeline", log_prints=True)
def ingestion_pipeline(file_names: list[str], env: str = "dev") -> None:
    """End-to-end ingestion pipeline for research paper PDFs.

    Args:
        file_names: PDF file names (relative to ``data/{env}/pdfs/``) to ingest.
        env: Environment name used for path resolution.

    Orchestrates: parse & chunk -> clean -> create documents -> embed -> upsert.
    """
    logger = get_run_logger()
    logger.info(f"Starting ingestion pipeline (env={env}, files={file_names})")

    data_dir = ROOT_DIR / "data" / env
    input_dir = data_dir / "pdfs"
    parsed_dir = data_dir / "parsed"
    cleaned_dir = data_dir / "cleaned"

    file_paths = [input_dir / name for name in file_names]

    parsed_paths = parse_and_chunk(file_paths=file_paths, output_dir=parsed_dir)
    cleaned_paths = clean_chunks(parsed_paths, output_dir=cleaned_dir)
    documents = create_documents(cleaned_paths)
    vectors = embed(documents)
    upsert_to_pinecone(vectors, env=env)

    logger.info("Ingestion pipeline complete")
