"""Entry point for the generation pipeline.

Usage:
    python scripts/run_generation.py --query "How does the Transformer use self-attention?"
    python scripts/run_generation.py --query "Compare BERT and GPT pre-training" --env prod
"""

import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generation_flow import generation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the generation pipeline")
    parser.add_argument(
        "--query",
        required=True,
        help="Natural language question to answer",
    )
    parser.add_argument(
        "--env",
        default="dev",
        choices=["dev", "prod"],
        help="Environment to run against (default: dev)",
    )
    args = parser.parse_args()

    result = generation(query=args.query, env=args.env)

    print(f"\n{'=' * 60}")
    print("ANSWER")
    print(f"{'=' * 60}")
    print(result["answer"])

    print(f"\n{'=' * 60}")
    print("SOURCES")
    print(f"{'=' * 60}")
    for src in result["sources"]:
        print(
            f"  [{src['source_number']}] {src['paper_title']} "
            f"| Section: {src.get('section', '—')} "
            f"| Page: {src.get('page_number', '—')}"
        )


if __name__ == "__main__":
    main()
