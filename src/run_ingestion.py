"""Entry point for the ingestion pipeline.

Usage:
    python -m src.run_ingestion
    python -m src.run_ingestion --env prod
    python -m src.run_ingestion --batch-size 3
"""

import argparse
import math
from pathlib import Path

from src.ingestion_flow import ingestion_pipeline

ROOT_DIR = Path(__file__).parent.parent.resolve()


def _discover_pdfs(input_dir: Path) -> list[str]:
    """Return sorted list of PDF file names in input_dir."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    return sorted(f.name for f in input_dir.iterdir() if f.suffix.lower() == ".pdf")


def _batch(items: list[str], size: int) -> list[list[str]]:
    """Split items into batches of at most `size`."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ingestion pipeline")
    parser.add_argument(
        "--env",
        default="dev",
        choices=["dev", "prod"],
        help="Environment to run against (default: dev)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Max number of PDFs per pipeline run (default: 5)",
    )
    args = parser.parse_args()

    input_dir = ROOT_DIR / "data" / args.env / "pdfs"
    all_files = _discover_pdfs(input_dir)

    if not all_files:
        print(f"No PDF files found in {input_dir}")
        return

    batches = _batch(all_files, args.batch_size)
    total = len(batches)
    print(f"Found {len(all_files)} PDF(s) — processing in {total} batch(es) of up to {args.batch_size}")

    for idx, batch in enumerate(batches, start=1):
        print(f"\n--- Batch {idx}/{total}: {batch} ---")
        ingestion_pipeline(file_names=batch, env=args.env)


if __name__ == "__main__":
    main()
