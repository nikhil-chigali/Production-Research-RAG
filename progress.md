# Progress

## Project overview

HybridRAG-Bench is a hybrid RAG pipeline for research papers. The current focus is on building a robust **ingestion pipeline** that parses, chunks, embeds, and stores PDFs for downstream retrieval. The pipeline is orchestrated with Prefect and uses LangChain as the document abstraction layer.

## Parsing & chunking experiments

All experiments used the **Unstructured.io cloud API** (on-demand jobs) against a research paper PDF.

### Run 1 — `hi_res` strategy, default settings

| Setting | Value |
|---|---|
| Partitioner | `hi_res` |
| Chunking | `chunk_by_title` |
| `max_characters` | 2000 |
| `new_after_n_chars` | 1600 |
| `overlap` | 200 |
| `combine_under_n_chars` | 50 |

**Observations:** Chunks were created but lacked contextual information. Some sections were split awkwardly across headings. Noise from headers, arXiv IDs, and inline page numbers was present.

### Run 2 — removed `combine_under_n_chars`

Removed `combine_under_n_chars` to let it default to `max_characters`. No visible change in output quality or chunk count — the parameter was effectively a no-op at the value used.

### Run 3 (final) — VLM strategy + contextual chunking + table enrichment

| Setting | Value |
|---|---|
| Partitioner | `vlm` (`is_dynamic=True`) |
| `exclude_elements` | `["Header"]` |
| Chunking | `chunk_by_title` |
| `max_characters` | 2048 |
| `new_after_n_chars` | 1500 |
| `overlap` | 160 |
| `overlap_all` | `false` |
| `include_orig_elements` | `false` |
| `multipage_sections` | `true` |
| `contextual_chunking_strategy` | `v1` |
| Prompter | `anthropic_table2html` (Claude Sonnet) |

**Key improvements over Run 1/2:**
- **Contextual prefixes** — each chunk receives a `Prefix: <paper title> > <section> > <subsection>` header, providing retrieval-friendly context
- **Better figure handling** — figures are described as Mermaid-style diagrams instead of garbled OCR
- **LaTeX equations** — mathematical content is rendered in LaTeX notation
- **Table enrichment** — tables are converted to clean HTML via Claude Sonnet, preserving structure
- **Section isolation** — chunks respect section boundaries more cleanly

## Results assessment (Run 3)

- **28 chunks** produced from the test PDF
- Each chunk carries a contextual prefix with paper title, section hierarchy
- Tables rendered as HTML with proper headers and data
- Equations preserved in LaTeX notation
- Mermaid-style descriptions for figure content

**Remaining noise to clean:**
- arXiv ID stamps (e.g., `arXiv:XXXX.XXXXX`)
- Inline page numbers
- Reference-only chunks (bibliography sections)
- Attention visualization / appendix chunks with limited retrieval value
- Short chunks below a useful token threshold

## Finalized settings

The configuration used going forward is stored in `configs/config.yaml` and loaded by `src/utils/ingest_config.py`. See Run 3 above for the exact values.

## Pipeline architecture

The ingestion pipeline is orchestrated with **Prefect** and structured as:

```
parse_and_chunk → clean_chunks → create_documents → embed → upsert_to_pinecone
```

- `src/ingestion_steps/parse_and_chunk.py` — implemented (Unstructured on-demand jobs API)
- `src/ingestion_flow.py` — main Prefect flow with placeholder tasks
- `src/run_ingestion.py` — CLI entry point

## Next steps

1. **Cleaning** — implement `clean_chunks` task: strip arXiv stamps, remove inline page numbers, drop reference/visualization chunks, filter by minimum token count
2. **Document creation** — implement `create_documents` task: split the contextual prefix into structured metadata (`paper_title`, `section`), extract `page_number`, `has_table`, `chunk_index`, build LangChain `Document` objects
3. **Metadata enrichment** — extract `authors`, `venue`, `year` from first-page content or filename conventions; attach `context_prefix` as separate metadata field
4. **Embedding** — implement `embed` task: dense vectors via OpenAI `text-embedding-3-small` (1536-dim), sparse vectors via `pinecone-text` BM25Encoder
5. **Upsert** — implement `upsert_to_pinecone` task: batch upsert hybrid vectors into Pinecone serverless index

## Tech stack

| Layer | Tool |
|---|---|
| Document parsing | Unstructured.io (VLM cloud API) |
| Chunking | `chunk_by_title` (Unstructured API) with contextual prefixes |
| Embeddings | OpenAI `text-embedding-3-small` |
| Sparse vectors | `pinecone-text` BM25Encoder |
| Vector store | Pinecone (serverless) |
| Orchestration | Prefect |
| Framework | LangChain |
| Language | Python >= 3.12 |
