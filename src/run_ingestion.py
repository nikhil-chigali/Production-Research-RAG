"""Entry point for the ingestion pipeline.

Usage:
    python -m src.run_ingestion
    python -m src.run_ingestion --env prod
"""

import argparse

from src.ingestion_flow import ingestion_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ingestion pipeline")
    parser.add_argument(
        "--env",
        default="dev",
        choices=["dev", "prod"],
        help="Environment to run against (default: dev)",
    )
    args = parser.parse_args()
    ingestion_pipeline(env=args.env)


if __name__ == "__main__":
    main()
