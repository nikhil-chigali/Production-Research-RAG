from dotenv import load_dotenv
from prefect import flow, get_run_logger

from src.generation_steps import retrieve, format_context, generate_answer

load_dotenv()


@flow(name="generation", log_prints=True)
def generation(query: str, env: str = "dev") -> dict:
    """Single-turn Q&A generation over the paper corpus.

    Args:
        query: The user's natural language question.
        env: Environment name for index resolution.

    Orchestrates: retrieve -> format_context -> generate_answer.
    Returns a dict with the generated answer and structured sources.
    """
    logger = get_run_logger()
    logger.info(f"Starting generation (env={env}, query={query!r})")

    documents = retrieve(query=query, env=env)
    context = format_context(documents=documents)
    result = generate_answer(query=query, context=context, documents=documents)

    logger.info("Generation complete")
    return result
