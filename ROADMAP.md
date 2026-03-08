# Roadmap

## v1 — Q&A with citations (implemented)

Single-turn question answering over the paper corpus. User asks a question, system retrieves relevant chunks via hybrid search (dense + sparse), LLM synthesizes an answer. Every claim links back to the source paper, section, and page number using chunk metadata (`paper_title`, `section`, `page_number`). Implemented as the generation pipeline: `retrieve → format_context → generate_answer` using OpenAI `gpt-4o-mini`.

## Generation Phase 2 — Query intelligence

Add query decomposition before retrieval for complex multi-topic questions.

**Task: `generate_search_queries`** (`src/generation_steps/generate_search_queries.py`) — Structured LLM call (OpenAI `gpt-4o-mini`) that decides whether the user's query needs decomposition. Simple queries pass through as-is; complex queries (e.g., "Compare BERT and Transformer attention") are split into targeted sub-queries. Output: `{"needs_decomposition": bool, "queries": list[str]}`.

**Changes to `retrieve`:** Run hybrid search per generated query, then deduplicate results by `element_id`. Merge using simple union (or Reciprocal Rank Fusion if ranking matters).

## Generation Phase 3 — Guardrails

Add input validation to reject off-topic queries before retrieval.

**Task: `evaluate_query`** (`src/generation_steps/evaluate_query.py`) — Structured LLM call (OpenAI `gpt-4o-mini`, short prompt) that classifies the query as relevant or not to the research paper corpus. Returns `{"is_relevant": bool, "reason": str}`. If not relevant, the flow short-circuits with a polite refusal message instead of running retrieval.

## v2 — Multi-turn conversation

Add conversation memory so follow-up questions maintain context (e.g., "What about their fine-tuning approach?" without re-stating the paper). LangChain conversation chain with retrieval.

## v3 — Multi-paper synthesis

Queries that span multiple papers: "Compare how BERT and GPT handle pre-training." Retrieves from multiple documents and synthesizes a comparative answer. This is where hybrid retrieval (dense + sparse) adds the most value -- semantic similarity for meaning, BM25 for keyword precision across documents.

## v4 — Paper summarization

"Summarize the QLoRA paper." Retrieve all chunks filtered by `paper_title` in Pinecone and generate a structured summary (problem, method, results, limitations). Uses metadata filtering rather than pure similarity search.

## v5 — Table/figure-specific Q&A

"What does Table 2 in the BERT paper show?" Leverage the HTML table enrichment from the ingestion pipeline (Anthropic table-to-HTML). Most RAG demos can't handle structured table content -- this is a differentiator.

**Ingestion improvement: include `text_as_html` in `page_content`.** For table chunks, append the structured HTML table after the original narrative text so the LLM can read actual row/column data instead of flattened OCR gibberish. Caveats to address:

- HTML tables are verbose (2-3k chars) and will increase chunk size — verify table chunks stay within the embedding model's 8191-token limit.
- HTML tags (`<table>`, `<tr>`, `<td>`) are semantically empty noise for the embedding model — measure whether retrieval quality for table queries improves or degrades after the change.
- The change belongs in `create_documents.py` where `page_content` is set; non-table chunks are unaffected.

## v6 — Concept explanation with evidence

"Explain knowledge distillation and which papers discuss it." Combines retrieval with a pedagogical generation style, pulling evidence across the corpus.

## Engineering qualities to add

- **Evaluation harness** — Build a small eval set (10-20 question/answer pairs with ground-truth source chunks). Measure retrieval recall (are the right chunks retrieved?) and answer quality (faithfulness, relevance). This is the single most impressive thing to show in an interview or report.
- **Observability** — Prefect handles pipeline observability. Add LLM call tracing on the query side (LangSmith or similar) to track latency, token usage, and retrieval quality per query.
- **Configurable retrieval** — ~~Expose retrieval parameters (top-k, alpha for hybrid weighting, reranking) via the YAML config.~~ Done: `retrieval.top_k` and `retrieval.alpha` are in `config.yaml`. Reranking is a future addition.

## Streamlit UI (implemented)

Two-tab web application (`streamlit run app.py`) wrapping the existing pipelines. Tab 1 is a file manager for uploading PDFs and triggering ingestion with real-time progress. Tab 2 is a chat interface for Q&A with expandable source citations. Sidebar toggle switches between `dev` and `prod` environments. Processing state auto-detects files ingested via CLI or notebooks through fuzzy filename matching.

## Recommended build order

1. ~~v1 (Q&A with citations)~~ — done
2. ~~Streamlit UI~~ — done
3. Generation Phase 2 (query decomposition) — improves multi-topic retrieval
4. Generation Phase 3 (guardrails) — rejects off-topic queries
5. v2 (multi-turn) — low effort, big UX improvement
6. Evaluation harness — makes everything measurable and defensible
7. v3 (multi-paper synthesis) — showcases hybrid retrieval
8. v4-v6 as stretch goals
