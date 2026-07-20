---
name: rag-development
description: Build and evolve the Embedded Copilot RAG pipeline under rag/. Use for PDF ingestion, document parsing and chunking, embeddings, Chroma persistence, retriever design, metadata filtering, source citations, and retrieval-quality tests.
---

# RAG Development

Build retrieval as a deterministic pipeline with provenance at every stage.

## Workflow

1. Parse PDFs into page-aware documents and record file, page, section, and checksum metadata.
2. Normalize text without deleting technical tokens, register names, code, tables, or units.
3. Split by document structure first and token budget second; retain configurable overlap.
4. Generate embeddings behind an interface so production and test implementations are replaceable.
5. Persist chunks and metadata in Chroma using stable document and chunk identifiers.
6. Retrieve with configurable top-k and filters; separate retrieval from answer generation.
7. Return citations with every grounded answer and refuse unsupported claims.
8. Test ingestion idempotency, chunk boundaries, metadata, ranking, empty results, and citation propagation.

## v0.1.0 Constraints

- Accept PDF as the first ingestion format.
- Use Chroma as the vector store behind a repository abstraction.
- Keep embedding provider selection in configuration.
- Store source path, page number, chunk index, content hash, and optional section title.
- Make ingestion repeatable without duplicate vectors.
- Surface parsing and indexing failures explicitly; never silently skip documents.
- Keep a small deterministic corpus for retriever tests.
- Do not require live embedding or model APIs in unit tests.

## Citation Contract

Each retrieved item must expose an identifier, text, relevance score, and source metadata. Final answers must link claims to these source records. If no relevant item meets the configured threshold, return an explicit insufficient-context result.

## Guardrails

- Do not mix parsing, embedding, storage, retrieval, and response synthesis in one module.
- Do not hard-code model names, chunk sizes, paths, or collection names.
- Do not claim that similarity scores are calibrated probabilities.
- Do not discard firmware code blocks, register names, pin names, or hexadecimal values during normalization.
