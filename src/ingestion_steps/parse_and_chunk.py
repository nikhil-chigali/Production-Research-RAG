import os
import json
import time
from pathlib import Path

from prefect import task, get_run_logger
from unstructured_client import UnstructuredClient
from unstructured_client.models.operations import (
    CreateJobRequest,
    DownloadJobOutputRequest,
)
from unstructured_client.models.shared import BodyCreateJob, InputFiles

from src.utils.ingest_config import get_config


def _build_job_nodes(cfg) -> list[dict]:
    return [
        {
            "name": "Partitioner",
            "type": "partition",
            "subtype": cfg.partitioning.strategy,
            "settings": {
                "is_dynamic": cfg.partitioning.is_dynamic,
                "exclude_elements": list(cfg.partitioning.exclude_elements),
            },
        },
        {
            "name": "Chunker",
            "type": "chunk",
            "subtype": cfg.chunking.strategy,
            "settings": {
                "max_characters": cfg.chunking.max_characters,
                "new_after_n_chars": cfg.chunking.new_after_n_chars,
                "overlap": cfg.chunking.overlap,
                "overlap_all": cfg.chunking.overlap_all,
                "include_orig_elements": cfg.chunking.include_orig_elements,
                "multipage_sections": cfg.chunking.multipage_sections,
                "contextual_chunking_strategy": cfg.chunking.contextual_chunking_strategy,
            },
        },
        {
            "name": "Table to HTML",
            "type": "prompter",
            "subtype": cfg.table_enrichment.subtype,
            "settings": {
                "model": cfg.table_enrichment.model,
            },
        },
    ]


def _run_on_demand_job(
    client: UnstructuredClient,
    input_dir: Path,
    job_nodes: list[dict],
) -> tuple[str, list[str]]:
    """Submit PDFs to the Unstructured on-demand jobs API."""
    logger = get_run_logger()
    files = []

    for filename in os.listdir(input_dir):
        full_path = os.path.join(input_dir, filename)
        if not os.path.isfile(full_path):
            continue
        files.append(
            InputFiles(
                content=open(full_path, "rb"),
                file_name=filename,
                content_type="application/pdf",
            )
        )

    if not files:
        raise FileNotFoundError(f"No files found in {input_dir}")

    request_data = json.dumps({"job_nodes": job_nodes})

    response = client.jobs.create_job(
        request=CreateJobRequest(
            body_create_job=BodyCreateJob(
                request_data=request_data,
                input_files=files,
            )
        )
    )

    job_id = response.job_information.id
    job_input_file_ids = response.job_information.input_file_ids
    logger.info(f"Created job {job_id} with {len(job_input_file_ids)} input file(s)")
    return job_id, job_input_file_ids


def _poll_for_job_status(
    client: UnstructuredClient,
    job_id: str,
    poll_interval: int = 10,
) -> str:
    """Poll until the job completes. Returns the final status string."""
    logger = get_run_logger()

    while True:
        response = client.jobs.get_job(request={"job_id": job_id})
        status = response.job_information.status

        if status in ("SCHEDULED", "IN_PROGRESS"):
            logger.info(f"Job {job_id} is {status}, polling again in {poll_interval}s...")
            time.sleep(poll_interval)
        else:
            logger.info(f"Job {job_id} finished with status: {status}")
            return status


def _download_job_output(
    client: UnstructuredClient,
    job_id: str,
    job_input_file_ids: list[str],
    output_dir: Path,
) -> list[Path]:
    """Download parsed+chunked JSON for each input file. Returns output paths."""
    logger = get_run_logger()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []

    for file_id in job_input_file_ids:
        response = client.jobs.download_job_output(
            request=DownloadJobOutputRequest(
                job_id=job_id,
                file_id=file_id,
            )
        )

        output_path = output_dir / f"{file_id}.json"
        with open(output_path, "w") as f:
            json.dump(response.any, f, indent=4)

        logger.info(f"Saved output for '{file_id}' -> {output_path}")
        output_paths.append(output_path)

    return output_paths


@task(name="parse_and_chunk", retries=1, log_prints=True)
def parse_and_chunk(input_dir: Path, output_dir: Path) -> list[Path]:
    """Parse PDFs via Unstructured VLM API and chunk by title.

    Submits all PDFs in input_dir to the Unstructured on-demand jobs API,
    polls until the job completes, and downloads the chunked output JSON
    files to output_dir.

    Returns a list of output JSON file paths.
    """
    logger = get_run_logger()
    cfg = get_config()
    job_nodes = _build_job_nodes(cfg)

    api_key = os.getenv("UNSTRUCTURED_API_KEY")
    if not api_key:
        raise EnvironmentError("UNSTRUCTURED_API_KEY is not set")

    with UnstructuredClient(api_key_auth=api_key) as client:
        logger.info(f"Submitting PDFs from {input_dir}")
        job_id, file_ids = _run_on_demand_job(client, input_dir, job_nodes)

        status = _poll_for_job_status(client, job_id)
        if status != "COMPLETED":
            raise RuntimeError(f"Job {job_id} ended with status: {status}")

        output_paths = _download_job_output(client, job_id, file_ids, output_dir)

    logger.info(f"Parse & chunk complete: {len(output_paths)} file(s) processed")
    return output_paths
