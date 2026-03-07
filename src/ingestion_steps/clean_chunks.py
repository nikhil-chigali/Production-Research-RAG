from pathlib import Path

from prefect import task, get_run_logger


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
