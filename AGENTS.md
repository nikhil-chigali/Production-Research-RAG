# AGENTS.md — Session Checkpoint

## Project Overview

HybridRAG-Bench is an enterprise RAG pipeline for research papers. The **ingestion pipeline** parses, chunks, cleans, embeds, and upserts PDFs into a Pinecone hybrid index. The **generation pipeline** retrieves relevant chunks via hybrid search, formats them as context, and generates cited answers via an LLM. The stack is Unstructured.io VLM cloud API, LangChain, Prefect, OpenAI (`text-embedding-3-small` for embeddings, `gpt-4o-mini` for generation), Pinecone (serverless), and Python >= 3.12.

## Current State

Implemented and verified:

- **`parse_and_chunk`** — Submits PDFs to Unstructured on-demand jobs API (VLM strategy, `chunk_by_title`, contextual chunking v1, Claude `anthropic_table2html`). Polls for completion, downloads chunked JSON to `data/{env}/parsed/`.
- **`clean_chunks`** — Reads parsed JSON, applies text-level fixes (OCR ligature normalization, garbled arXiv stamp removal, inline page number stripping, equation number removal, whitespace collapsing), drops reference/bibliography chunks, garbled figure chunks (`<EOS>`/`<pad>` or >30% word repetition), and chunks below `min_chunk_length` (default 50). Writes cleaned JSON to `data/{env}/cleaned/`.
- **`create_documents`** — Reads cleaned JSON, splits `Prefix: ...; Original: ...` text on `"; Original: "`. Builds LangChain `Document` objects with `page_content` = original text only (not prefix). Metadata: `context_prefix`, `paper_title` (regex-extracted quoted title), `section` (first-line heading detection), `page_number`, `source_filename`, `has_table`, `chunk_index`, `element_id`.
- **`embed`** — Generates dense embeddings (OpenAI `text-embedding-3-small`, 1536-dim, batched) and sparse embeddings (`pinecone-text` BM25Encoder, MS MARCO pre-trained). Embeds contextually enriched text (prefix + original). Returns Pinecone-ready vector records (`id`, `values`, `sparse_values`, `metadata`). Config: `embedding.model`, `embedding.dimensions`, `embedding.batch_size` in `config.yaml`.
- **`upsert_to_pinecone`** — Connects to or creates a Pinecone serverless index named `arxiv-research-rag-{env}` (dotproduct metric, 1536-dim). Batch-upserts hybrid vector records (dense + sparse + metadata). Index creation is idempotent — skipped if the index already exists. Config: `pinecone.index_name_prefix`, `pinecone.cloud`, `pinecone.region`, `pinecone.metric`, `pinecone.upsert_batch_size` in `config.yaml`.
- **Prefect flow** — `src/ingestion_flow.py` orchestrates all 5 tasks in sequence. No task definitions in this file.
- **Batched entry point** — `scripts/run_ingestion.py` discovers PDFs in `data/{env}/pdfs/`, batches them (default 5), invokes the flow per batch. CLI args: `--env` (dev/prod), `--batch-size`.
- **YAML config** — `configs/config.yaml` loaded by `src/utils/ingest_config.py` via `ml_collections.ConfigDict`. Sections: `partitioning`, `chunking`, `table_enrichment`, `cleaning`, `embedding`, `pinecone`, `retrieval`, `generation`, `paths`.
- **Notebook runner** — `notebooks/ingest.ipynb` has test cells for `parse_and_chunk`, `clean_chunks`, `create_documents`, `embed`, and `upsert_to_pinecone` (each wrapped in a thin Prefect flow).
- **Dev data** — 2 papers parsed and cleaned: Attention Is All You Need (28 → 16 chunks), BERT (44 → 37 chunks).
- **`retrieve`** — Wraps `PineconeHybridSearchRetriever` in a Prefect `@task`. Hybrid search (dense + sparse) with tunable alpha. Config: `retrieval.top_k`, `retrieval.alpha`.
- **`format_context`** — Formats retrieved documents as numbered `[Source N]` blocks for LLM consumption.
- **`generate_answer`** — Calls OpenAI `gpt-4o-mini` via `langchain-openai` with a RAG system prompt (`src/prompts/rag.py`). Returns `{"answer": str, "sources": list[dict]}`. Config: `generation.model`, `generation.temperature`, `generation.max_tokens`.
- **Generation flow** — `src/generation_flow.py` chains `retrieve → format_context → generate_answer`.
- **Generation entry point** — `scripts/run_generation.py` CLI with `--query` and `--env` args.
- **Generation notebook** — `notebooks/generate.ipynb` has test cells for `retrieve`, `format_context`, and `generate_answer`.

## Active Architecture

```
├── configs/config.yaml              # All pipeline settings (YAML)
├── src/
│   ├── ingestion_steps/             # One @task per file, exported via __init__.py
│   │   ├── parse_and_chunk.py       # Unstructured on-demand jobs API
│   │   ├── clean_chunks.py          # Text cleaning + drop filters
│   │   ├── create_documents.py      # JSON → LangChain Document objects
│   │   ├── embed.py                 # Dense (OpenAI) + sparse (BM25) embeddings
│   │   └── upsert_to_pinecone.py    # Pinecone index creation + batch upsert
│   ├── ingestion_flow.py            # @flow orchestration only
│   ├── generation_steps/            # One @task per file, exported via __init__.py
│   │   ├── retrieve.py              # Hybrid search (dense + sparse)
│   │   ├── format_context.py        # Context formatting for LLM
│   │   └── generate_answer.py       # LLM answer with citations (OpenAI gpt-4o-mini)
│   ├── generation_flow.py           # @flow: retrieve → format_context → generate_answer
│   ├── prompts/
│   │   └── rag.py                   # QA_PROMPT ChatPromptTemplate
│   ├── utils/ingest_config.py       # get_config() → ConfigDict
│   └── constants.py                 # Path helpers (ENV env var)
├── scripts/
│   ├── run_ingestion.py             # CLI entry point (batch discovery)
│   └── run_generation.py            # CLI entry point (--query, --env)
├── data/{env}/
│   ├── pdfs/                        # Input PDFs
│   ├── parsed/                      # Raw chunked JSON from Unstructured
│   └── cleaned/                     # Post-cleaning JSON
├── notebooks/
│   ├── ingest.ipynb                 # Ingestion step-by-step runner
│   └── generate.ipynb               # Generation step-by-step runner
├── progress.md                      # Project journey documentation
└── ROADMAP.md                       # Future RAG capabilities (v1-v6)
```

**Patterns:**
- Every ingestion step is a Prefect `@task` in its own file under `src/ingestion_steps/`.
- Every generation step is a Prefect `@task` in its own file under `src/generation_steps/`.
- Flow files (`ingestion_flow.py`, `generation_flow.py`) only import and chain tasks — no logic.
- Config is YAML-first; `get_config()` returns a `ConfigDict` with dot-access. Sections: `partitioning`, `chunking`, `table_enrichment`, `cleaning`, `embedding`, `pinecone`, `retrieval`, `generation`, `paths`.
- Chunk text uses `"Prefix: <summary>; Original: <content>"` format. Split on `"; Original: "`.
- Embedding text is contextually enriched: `prefix + ". " + original`. This bakes section hierarchy and paper title into the vectors.

## Pending Tasks

1. Metadata enrichment — Extract `authors`, `venue`, `year` from first-page chunk content or filename conventions.
2. Generation Phase 2 — Query decomposition (`generate_search_queries` task) for complex multi-topic questions.
3. Generation Phase 3 — Input guardrails (`evaluate_query` task) to reject off-topic queries.

## Crucial Context

- **Unstructured API** uses on-demand jobs (submit → poll → download), NOT the partition endpoint. The `_run_on_demand_job`, `_poll_for_job_status`, `_download_job_output` helpers are in `parse_and_chunk.py`.
- **Garbled figure OCR** (e.g., `Qutput Probabilities Multi-Head Attention...`, `Mask LM Mask LM...`) remains in otherwise-good chunks. Accepted as a known limitation — the surrounding narrative text is clean.
- **Unicode math symbols** (`−`, `∞`, `√`) are intentional content, not noise. Do NOT clean them.
- **OCR ligatures** (`ﬁ` → `fi`, `ﬂ` → `fl`) ARE cleaned. Double newlines (`\n\n`) are preserved as paragraph separators.
- **Environment variables required:** `UNSTRUCTURED_API_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY` (loaded via `python-dotenv`).
- **Parsing experiments:** 3 iterations documented in `progress.md`. Final: VLM strategy + contextual chunking v1 + Claude table-to-HTML. Do not change these settings without re-evaluating.
- **`clean_chunks` writes to disk** (`data/{env}/cleaned/`) and returns paths. `create_documents` reads from disk and returns in-memory `list[Document]`. From `create_documents` onward, data flows in-memory.
- **`embed` embeds contextually enriched text** (prefix + original) so vectors capture section/paper context. Dense via OpenAI, sparse via BM25 (MS MARCO pre-trained, no corpus fitting needed). Returns Pinecone-ready dicts. `None` metadata values are stripped before upsert.
- **`upsert_to_pinecone` creates the index if needed** (`_ensure_index`), using `ServerlessSpec(cloud, region)` and `dotproduct` metric (required for hybrid search). Index name is `arxiv-research-rag-{env}`. Upserts are idempotent by vector `id` — re-ingesting the same paper overwrites, not duplicates. All vectors go into the default namespace.
- **`generate_answer` uses OpenAI `gpt-4o-mini`** via `langchain_openai.ChatOpenAI`. The RAG prompt (`src/prompts/rag.py`) is a `ChatPromptTemplate` with `{context}` and `{query}` variables. The LLM is instructed to answer only from sources and cite as `[Source N]`. Returns `{"answer", "sources"}` where sources are extracted from document metadata.
- **Prompt management** — `src/prompts/` contains `ChatPromptTemplate` objects as module-level constants. Keeps prompts version-controlled and separated from task logic.
- **Notebook** (`ingest.ipynb`) uses `Path.cwd().parent` as `ROOT_DIR` and `os.chdir(ROOT_DIR)` in cell 0. The `flow` import is shared across cells.
