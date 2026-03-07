# Roadmap

## v1 — Q&A with citations

Single-turn question answering over the paper corpus. User asks a question, system retrieves relevant chunks via hybrid search (dense + sparse), LLM synthesizes an answer. Every claim links back to the source paper, section, and page number using chunk metadata (`paper_title`, `section`, `page_number`).

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
- **Configurable retrieval** — Expose retrieval parameters (top-k, alpha for hybrid weighting, reranking) via the YAML config. Being able to A/B test settings and show measured improvements is a strong talking point.

## Recommended build order

1. v1 (Q&A with citations) — proves the pipeline works end-to-end
2. v2 (multi-turn) — low effort, big UX improvement
3. Evaluation harness — makes everything measurable and defensible
4. v3 (multi-paper synthesis) — showcases hybrid retrieval
5. v4-v6 as stretch goals
