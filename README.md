# Research Paper Enterprise RAG Pipeline

A hybrid RAG pipeline for research papers with end-to-end ingestion and cited Q&A generation. PDFs are parsed, chunked, embedded, and stored in a Pinecone hybrid index. User queries retrieve relevant chunks via hybrid search (dense + sparse) and generate cited answers via OpenAI `gpt-4o-mini`.

## Current scope

The project has two pipelines and a web UI:

- **Ingestion pipeline** — Takes PDF documents from `data/{env}/pdfs/`, parses them via the Unstructured.io **VLM cloud API**, chunks with `by_title` strategy and contextual prefixes, generates dense (OpenAI `text-embedding-3-small`) and sparse (BM25) embeddings, and upserts hybrid vectors into Pinecone.
- **Generation pipeline** — Retrieves relevant chunks via hybrid search, formats them as numbered source blocks, and generates an answer with `[Source N]` citations via OpenAI `gpt-4o-mini`.
- **Streamlit UI** — A two-tab web application for managing PDFs (upload, view processing status, trigger ingestion) and chatting with the paper corpus (Q&A with expandable source citations).

Both pipelines are orchestrated with **Prefect** and use **LangChain** as the integration layer.

## Tech stack

| Layer | Tool |
|---|---|
| Document parsing | Unstructured.io (VLM cloud API) |
| Chunking | `chunk_by_title` (Unstructured API) with contextual prefixes |
| Embeddings | OpenAI `text-embedding-3-small` |
| Sparse vectors | `pinecone-text` BM25Encoder |
| Vector store | Pinecone (serverless) |
| Generation LLM | OpenAI `gpt-4o-mini` (via `langchain-openai`) |
| Orchestration | Prefect |
| Framework | LangChain |
| Web UI | Streamlit |
| Language | Python >= 3.12 |

## Project structure

```
├── app.py                     # Streamlit entry point
├── data/                      # Input PDFs ({env}/pdfs/) and parsed outputs ({env}/parsed/)
├── artifacts/                 # Intermediate outputs (BM25 encoder, etc.)
├── configs/
│   └── config.yaml            # YAML-based configuration
├── src/
│   ├── constants.py           # Path definitions
│   ├── utils/
│   │   └── ingest_config.py   # Config loader from YAML
│   ├── ingestion_steps/       # Prefect tasks (one file per step)
│   │   ├── parse_and_chunk.py
│   │   ├── clean_chunks.py
│   │   ├── create_documents.py
│   │   ├── embed.py
│   │   └── upsert_to_pinecone.py
│   ├── ingestion_flow.py      # Ingestion Prefect flow
│   ├── generation_steps/      # Prefect tasks (one file per step)
│   │   ├── retrieve.py
│   │   ├── format_context.py
│   │   └── generate_answer.py
│   ├── generation_flow.py     # Generation Prefect flow
│   ├── prompts/
│   │   └── rag.py             # QA prompt template
│   └── ui/                    # Streamlit UI modules
│       ├── state.py           # Processing state tracker
│       ├── file_manager.py    # Tab 1: PDF management + ingestion
│       └── chat.py            # Tab 2: Q&A chat interface
├── scripts/
│   ├── run_ingestion.py       # Ingestion entry point (batch discovery)
│   └── run_generation.py      # Generation entry point (--query, --env)
├── notebooks/
│   ├── ingest.ipynb           # Ingestion step-by-step runner
│   └── generate.ipynb         # Generation step-by-step runner
└── pyproject.toml
```

## Ingestion pipeline

1. **Parse + Chunk** — PDFs are sent to the Unstructured.io VLM cloud API (`by_title` chunking, `contextual_chunking_strategy=v1`) with table-to-HTML enrichment via Claude.
2. **Clean** — Post-processing to strip noise (arXiv IDs, inline page numbers, garbled OCR) and filter out non-essential chunks (references, visualization appendices, short chunks).
3. **Document Objects** — Convert cleaned elements into LangChain `Document` objects with metadata (paper title, section, page number, etc.).
4. **Embed** — Each chunk is embedded via OpenAI `text-embedding-3-small` (1536-dim) and a BM25 sparse vector is generated in parallel.
5. **Store** — Dense and sparse vectors are upserted into a Pinecone serverless index for hybrid retrieval.

## Generation pipeline

1. **Retrieve** — Hybrid search (dense + sparse, alpha-weighted) against the Pinecone index. Returns top-k relevant chunks as LangChain `Document` objects.
2. **Format Context** — Formats retrieved documents into numbered `[Source N]` blocks with paper title, section, and page metadata.
3. **Generate Answer** — Sends the formatted context and user query to OpenAI `gpt-4o-mini` via a RAG prompt that enforces source-only answers with `[Source N]` citations.

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

## Usage

### Streamlit app (recommended)

```bash
streamlit run app.py
```

The app provides two tabs:

- **File Manager** — Upload PDFs, view processing status (auto-detects previously ingested files), select files, and trigger the ingestion pipeline with real-time progress.
- **Chat** — Ask questions about your ingested papers. Answers include `[Source N]` citations with expandable metadata (paper title, section, page number).

Use the sidebar radio toggle to switch between `dev` and `prod` environments.

### CLI

```bash
# run ingestion (dev environment, default batch size of 5)
python scripts/run_ingestion.py

# run against prod
python scripts/run_ingestion.py --env prod

# use a smaller batch size
python scripts/run_ingestion.py --batch-size 3
```

The entry point discovers all PDFs in `data/{env}/pdfs/` and processes them in batches (default: 5 files per batch) to keep API wait times manageable.

```bash
# ask a question (dev environment)
python scripts/run_generation.py --query "How does the Transformer use self-attention?"

# ask against prod
python scripts/run_generation.py --query "Compare BERT and GPT pre-training" --env prod
```
