# AGENTS.md — Session Checkpoint

## Project Overview

HybridRAG-Bench is an enterprise RAG pipeline for research papers, focused on ingesting PDFs (parse, chunk, clean, embed) and storing hybrid vectors for downstream retrieval. The stack is Unstructured.io VLM cloud API, LangChain, Prefect, OpenAI `text-embedding-3-small`, Pinecone (serverless), and Python >= 3.12.

## Current State

Implemented and verified:

- **`parse_and_chunk`** — Submits PDFs to Unstructured on-demand jobs API (VLM strategy, `chunk_by_title`, contextual chunking v1, Claude `anthropic_table2html`). Polls for completion, downloads chunked JSON to `data/{env}/parsed/`.
- **`clean_chunks`** — Reads parsed JSON, applies text-level fixes (OCR ligature normalization, garbled arXiv stamp removal, inline page number stripping, equation number removal, whitespace collapsing), drops reference/bibliography chunks, garbled figure chunks (`<EOS>`/`<pad>` or >30% word repetition), and chunks below `min_chunk_length` (default 50). Writes cleaned JSON to `data/{env}/cleaned/`.
- **`create_documents`** — Reads cleaned JSON, splits `Prefix: ...; Original: ...` text on `"; Original: "`. Builds LangChain `Document` objects with `page_content` = original text only (not prefix). Metadata: `context_prefix`, `paper_title` (regex-extracted quoted title), `section` (first-line heading detection), `page_number`, `source_filename`, `has_table`, `chunk_index`, `element_id`.
- **`embed`** — Generates dense embeddings (OpenAI `text-embedding-3-small`, 1536-dim, batched) and sparse embeddings (`pinecone-text` BM25Encoder, MS MARCO pre-trained). Embeds contextually enriched text (prefix + original). Returns Pinecone-ready vector records (`id`, `values`, `sparse_values`, `metadata`). Config: `embedding.model`, `embedding.dimensions`, `embedding.batch_size` in `config.yaml`.
- **`upsert_to_pinecone`** — Placeholder (no-op).
- **Prefect flow** — `src/ingestion_flow.py` orchestrates all 5 tasks in sequence. No task definitions in this file.
- **Batched entry point** — `src/run_ingestion.py` discovers PDFs in `data/{env}/pdfs/`, batches them (default 5), invokes the flow per batch. CLI args: `--env` (dev/prod), `--batch-size`.
- **YAML config** — `configs/config.yaml` loaded by `src/utils/ingest_config.py` via `ml_collections.ConfigDict`. Sections: `partitioning`, `chunking`, `table_enrichment`, `cleaning`, `embedding`, `paths`.
- **Notebook runner** — `notebooks/ingest.ipynb` has test cells for `parse_and_chunk`, `clean_chunks`, `create_documents`, and `embed` (each wrapped in a thin Prefect flow).
- **Dev data** — 2 papers parsed and cleaned: Attention Is All You Need (28 → 16 chunks), BERT (44 → 37 chunks).

## Active Architecture

```
├── configs/config.yaml              # All pipeline settings (YAML)
├── src/
│   ├── ingestion_steps/             # One @task per file, exported via __init__.py
│   │   ├── parse_and_chunk.py       # Unstructured on-demand jobs API
│   │   ├── clean_chunks.py          # Text cleaning + drop filters
│   │   ├── create_documents.py      # JSON → LangChain Document objects
│   │   ├── embed.py                 # Dense (OpenAI) + sparse (BM25) embeddings
│   │   └── upsert_to_pinecone.py    # Placeholder
│   ├── ingestion_flow.py            # @flow orchestration only
│   ├── run_ingestion.py             # CLI entry point (batch discovery)
│   ├── utils/ingest_config.py       # get_config() → ConfigDict
│   └── constants.py                 # Path helpers (ENV env var)
├── data/{env}/
│   ├── pdfs/                        # Input PDFs
│   ├── parsed/                      # Raw chunked JSON from Unstructured
│   └── cleaned/                     # Post-cleaning JSON
├── notebooks/ingest.ipynb           # Step-by-step runner and inspection
├── progress.md                      # Project journey documentation
└── ROADMAP.md                       # Future RAG capabilities (v1-v6)
```

**Patterns:**
- Every ingestion step is a Prefect `@task` in its own file under `src/ingestion_steps/`.
- The flow file (`ingestion_flow.py`) only imports and chains tasks — no logic.
- Config is YAML-first; `get_config()` returns a `ConfigDict` with dot-access. Sections: `partitioning`, `chunking`, `table_enrichment`, `cleaning`, `embedding`, `paths`.
- Chunk text uses `"Prefix: <summary>; Original: <content>"` format. Split on `"; Original: "`.
- Embedding text is contextually enriched: `prefix + ". " + original`. This bakes section hierarchy and paper title into the vectors.

## Pending Tasks

1. Metadata enrichment — Extract `authors`, `venue`, `year` from first-page chunk content or filename conventions.
2. Implement `upsert_to_pinecone` task — Batch upsert hybrid (dense + sparse) vectors into Pinecone serverless index with document metadata.

## Crucial Context

- **Unstructured API** uses on-demand jobs (submit → poll → download), NOT the partition endpoint. The `_run_on_demand_job`, `_poll_for_job_status`, `_download_job_output` helpers are in `parse_and_chunk.py`.
- **Garbled figure OCR** (e.g., `Qutput Probabilities Multi-Head Attention...`, `Mask LM Mask LM...`) remains in otherwise-good chunks. Accepted as a known limitation — the surrounding narrative text is clean.
- **Unicode math symbols** (`−`, `∞`, `√`) are intentional content, not noise. Do NOT clean them.
- **OCR ligatures** (`ﬁ` → `fi`, `ﬂ` → `fl`) ARE cleaned. Double newlines (`\n\n`) are preserved as paragraph separators.
- **Environment variables required:** `UNSTRUCTURED_API_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY` (loaded via `python-dotenv`).
- **Parsing experiments:** 3 iterations documented in `progress.md`. Final: VLM strategy + contextual chunking v1 + Claude table-to-HTML. Do not change these settings without re-evaluating.
- **`clean_chunks` writes to disk** (`data/{env}/cleaned/`) and returns paths. `create_documents` reads from disk and returns in-memory `list[Document]`. From `create_documents` onward, data flows in-memory.
- **`embed` embeds contextually enriched text** (prefix + original) so vectors capture section/paper context. Dense via OpenAI, sparse via BM25 (MS MARCO pre-trained, no corpus fitting needed). Returns Pinecone-ready dicts. `None` metadata values are stripped before upsert.
- **Notebook** (`ingest.ipynb`) uses `Path.cwd().parent` as `ROOT_DIR` and `os.chdir(ROOT_DIR)` in cell 0. The `flow` import is shared across cells.
