# Research Paper Enterprise RAG Pipeline

A hybrid RAG pipeline for research papers, starting with a document ingestion system that parses, chunks, and embeds PDFs for downstream retrieval. This is a proof of concept for a larger enterprise RAG pipeline for research papers.

## Current scope

The project is focused on the **ingestion pipeline**: taking PDF documents from the `data/{env}/pdfs/` directory, parsing them via the Unstructured.io **VLM cloud API**, chunking the extracted text with `by_title` strategy and contextual prefixes, and generating dense embeddings using OpenAI's `text-embedding-3-small`. The pipeline is orchestrated with **Prefect** and uses **LangChain** as the integration layer.

## Tech stack

| Layer | Tool |
|---|---|
| Document parsing | Unstructured.io (VLM cloud API) |
| Chunking | `by_title` strategy (Unstructured API), contextual prefixes, token-based (`tiktoken`, `cl100k_base` encoding) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Sparse vectors | `pinecone-text` BM25Encoder |
| Vector store | Pinecone (serverless) |
| Orchestration | Prefect |
| Framework | LangChain |
| Language | Python >= 3.12 |

## Project structure

```
├── data/                      # Input PDFs ({env}/pdfs/) and parsed outputs ({env}/parsed/)
├── artifacts/                 # Intermediate outputs (BM25 encoder, etc.)
├── configs/
│   └── config.yaml            # YAML-based configuration
├── src/
│   ├── constants.py           # Path definitions
│   ├── utils/
│   │   └── ingest_config.py   # Config loader from YAML
│   ├── ingestion_steps/       # Prefect tasks for pipeline steps
│   │   └── parse_and_chunk.py
│   ├── ingestion_flow.py      # Main Prefect flow
│   └── run_ingestion.py       # Entry point for the ingestion flow
├── main.py
└── pyproject.toml
```

## Ingestion pipeline

1. **Parse + Chunk** — PDFs are sent to the Unstructured.io VLM cloud API (`by_title` chunking, `contextual_chunking_strategy=v1`) with table-to-HTML enrichment via Claude.
2. **Clean** — Post-processing to strip noise (arXiv IDs, inline page numbers, garbled OCR) and filter out non-essential chunks (references, visualization appendices, short chunks).
3. **Document Objects** — Convert cleaned elements into LangChain `Document` objects with metadata (paper title, section, page number, etc.).
4. **Embed** — Each chunk is embedded via OpenAI `text-embedding-3-small` (1536-dim) and a BM25 sparse vector is generated in parallel.
5. **Store** — Dense and sparse vectors are upserted into a Pinecone serverless index for hybrid retrieval.

## Setup

```bash
# clone and install
git clone <repo-url>
cd HybridRAG-Bench
uv sync

# required environment variables
UNSTRUCTURED_API_KEY=...
OPENAI_API_KEY=...
PINECONE_API_KEY=...
```

Place PDF files in the `data/{env}/pdfs/` directory before running the pipeline.
