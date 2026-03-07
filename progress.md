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

Each pipeline step lives in its own module under `src/ingestion_steps/`:

- `parse_and_chunk.py` — implemented (Unstructured on-demand jobs API)
- `clean_chunks.py` — implemented (text cleaning + drop filters)
- `create_documents.py` — implemented (LangChain Document objects with structured metadata)
- `embed.py` — implemented (dense + sparse hybrid embeddings)
- `upsert_to_pinecone.py` — placeholder

Orchestration and entry point:

- `src/ingestion_flow.py` — main Prefect flow (orchestration only, no task definitions); accepts an explicit list of file names per run
- `src/run_ingestion.py` — CLI entry point that discovers PDFs in the input folder and invokes the flow in batches (default batch size: 5) to keep API wait times manageable

## Chunk cleaning (implemented)

The `clean_chunks` task (`src/ingestion_steps/clean_chunks.py`) reads parsed JSON, applies text-level fixes, drops low-value chunks, and writes cleaned JSON to `data/{env}/cleaned/`.

**Text-level cleaning (applied to every chunk):**
- Normalize OCR ligatures (`ﬁ` → `fi`, `ﬂ` → `fl`)
- Strip garbled arXiv watermark stamps (reversed OCR text containing `v i X r a`)
- Remove standalone inline page numbers (`\n\n5\n\n`, trailing `\n\n15`)
- Remove standalone equation number markers (`\n\n(1)\n\n`)
- Collapse excessive whitespace (3+ newlines → 2)

**Drop filters (chunk is removed entirely if any match):**
- Reference / bibliography chunks — detected by "References" heading or 4+ numbered `[N]` citations
- Garbled figure / attention visualization chunks — detected by `<EOS>`/`<pad>` tokens or high word-repetition ratio (>30%)
- Short chunks — original text below `min_chunk_length` characters (configurable in `config.yaml`, default 50)

## Document creation (implemented)

The `create_documents` task (`src/ingestion_steps/create_documents.py`) reads cleaned JSON from `data/{env}/cleaned/`, splits each chunk's `Prefix: ...; Original: ...` text, and builds LangChain `Document` objects.

**`page_content`** = original text only (the content after `; Original: `). The contextual prefix is stored separately in metadata as `context_prefix`, keeping the document body clean while preserving context for retrieval enrichment.

**Metadata fields extracted per chunk:**

| Field | Source |
|---|---|
| `context_prefix` | The contextual summary before `; Original: ` |
| `paper_title` | Quoted title extracted from the prefix via regex |
| `section` | First line of original if it matches a section heading pattern |
| `page_number` | From chunk metadata |
| `source_filename` | From chunk metadata |
| `has_table` | `True` if `text_as_html` exists in chunk metadata |
| `chunk_index` | 0-based positional index within each file |
| `element_id` | From chunk element ID |

## Embedding (implemented)

The `embed` task (`src/ingestion_steps/embed.py`) generates hybrid (dense + sparse) vectors for each LangChain `Document` and outputs Pinecone-ready vector records.

**Embedding text** is contextually enriched: `context_prefix + ". " + page_content`. This bakes the paper title and section hierarchy into the vectors, improving retrieval relevance.

**Dense embeddings** — OpenAI `text-embedding-3-small` (1536-dim). Texts are batched (default 100, configurable via `embedding.batch_size` in `config.yaml`) to minimize API calls.

**Sparse embeddings** — `pinecone-text` `BM25Encoder.default()`, pre-trained on MS MARCO. Each text is encoded into a sparse vector of token indices and BM25 weights.

**Output format** — each vector record is a dict with `id` (element_id from Unstructured), `values` (dense), `sparse_values` (sparse), and `metadata` (text, prefix, paper_title, section, page_number, etc.). `None` metadata values are stripped since Pinecone rejects them.

### BM25 strategy: MS MARCO defaults vs. corpus-fitted

We use `BM25Encoder.default()` which loads pre-trained IDF weights from MS MARCO rather than fitting on our own corpus. This is a deliberate trade-off:

**Why this works with batched ingestion:** Since the IDF weights are fixed (from MS MARCO), every batch of 5 PDFs uses the exact same encoder with the exact same weights. Vectors are consistent across batches with no cross-batch dependency. If we were fitting BM25 on our own corpus (`bm25.fit(all_documents)`), batching would be a problem — each batch would compute different IDF values, producing incomparable sparse vectors.

**Trade-off:** MS MARCO IDF values reflect a web search corpus, not academic papers. Terms like "transformer" or "attention" may be rare in MS MARCO (high IDF = important) but common across our paper corpus (should have lower IDF). This means BM25 may over-weight domain-common terms. In practice this is acceptable because dense embeddings carry the semantic heavy lifting and the hybrid weighting (alpha) at query time can be tuned to balance the two signals.

**Future improvement:** If BM25 retrieval quality needs tuning, switch to a corpus-fitted approach: fit once on the full corpus, serialize to `artifacts/bm25_params.json`, and load that fixed encoder in `_embed_sparse` instead of calling `.default()`. This would require a two-pass pipeline (fit first, then encode) but would give IDF values calibrated to academic paper vocabulary.

## Next steps

1. **Metadata enrichment** — extract `authors`, `venue`, `year` from first-page content or filename conventions
2. **Upsert** — implement `upsert_to_pinecone` task: batch upsert hybrid vectors into Pinecone serverless index

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
