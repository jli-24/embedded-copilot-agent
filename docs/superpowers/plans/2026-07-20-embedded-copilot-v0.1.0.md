# Embedded Copilot Agent v0.1.0 Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver an offline-testable Embedded Copilot Agent v0.1.0 with four LangGraph agents, cited PDF RAG, typed Tool Calling, and a FastAPI query interface.

**Architecture:** A small LangGraph workflow routes a typed request from Supervisor to one specialist. Knowledge uses the RAG retriever; Firmware and Debug may use retrieved context and registered tools. FastAPI is a thin boundary over the workflow. External model, embedding, vector-store, and hardware behavior is replaced with deterministic fakes in tests.

**Tech Stack:** Python 3.12, LangGraph, FastAPI, Pydantic v2, ChromaDB, PyMuPDF, pytest, HTTPX, Ruff, mypy.

## Global Constraints

- Target version is v0.1.0.
- Application development starts only after explicit user approval.
- Use TDD for every behavior change.
- Default tests must not require network access, API keys, hardware, or persistent user data.
- Preserve citations from PDF page ingestion through the API response.
- Allowed commit prefixes are feat:, fix:, docs:, and test:.
- Do not add a plugin framework, message broker, database server, UI, authentication system, or multiple vector-store backends in v0.1.0.

---

## File Structure Map

- pyproject.toml: package metadata, v0.1.0 dependencies, test and quality-tool configuration.
- core/config.py: Pydantic settings.
- core/logging.py: structured logging setup and trace context.
- models/contracts.py: shared request, response, citation, retrieval, and error models.
- agents/state.py: typed LangGraph state and route enum.
- agents/supervisor.py: constrained route selection.
- agents/knowledge.py: cited knowledge response node.
- agents/firmware.py: embedded firmware guidance node.
- agents/debug.py: evidence-labeled debugging node.
- agents/workflow.py: graph construction and invocation.
- rag/pdf_loader.py: page-aware PDF parsing.
- rag/chunking.py: structure and token-budget chunking.
- rag/index.py: Chroma ingestion and idempotency.
- rag/retriever.py: top-k retrieval and citation records.
- tools/contracts.py: typed tool input, output, and error models.
- tools/registry.py: explicit tool lookup and execution.
- api/main.py: FastAPI application and lifespan.
- api/schemas.py: public API contracts.
- api/routes.py: health and query endpoints.
- api/errors.py: exception-to-HTTP mapping.
- tests/: mirrored unit and API behavior tests.

### Task 1: Reproducible Python Project

**Files:**

- Create: pyproject.toml
- Create: .gitignore
- Create: .env.example
- Create: core/__init__.py
- Create: core/config.py
- Create: tests/core/test_config.py

**Interfaces:**

- Produce Settings with app_name, version, log_level, chroma_path, collection_name, retrieval_top_k, retrieval_score_threshold, and request_timeout_seconds.

- [ ] Write tests proving defaults equal the v0.1.0 values and invalid top-k, score threshold, or timeout values fail validation.
- [ ] Run `pytest tests/core/test_config.py -q`; expect failure because core.config does not exist.
- [ ] Add the minimum package configuration and Settings model.
- [ ] Run the focused test, Ruff, and mypy; expect all to pass.
- [ ] Commit with `feat: initialize Python project configuration`.

### Task 2: Shared Contracts and Typed Tools

**Files:**

- Create: models/__init__.py
- Create: models/contracts.py
- Create: tools/__init__.py
- Create: tools/contracts.py
- Create: tools/registry.py
- Create: tests/tools/test_registry.py

**Interfaces:**

- Produce Citation(source, page, chunk_id, score).
- Produce RetrievedChunk(id, text, citation).
- Produce CopilotRequest(query, conversation_id).
- Produce CopilotResponse(answer, route, citations, trace_id).
- Produce ToolResult with status success or error and a stable error code.
- Produce ToolRegistry.register(name, input_model, handler) and ToolRegistry.invoke(name, payload, timeout_seconds).

- [ ] Write tests for successful invocation, unknown tools, invalid input, handler errors, and timeouts.
- [ ] Run `pytest tests/tools/test_registry.py -q`; expect import failure.
- [ ] Implement the Pydantic contracts and one explicit registry dictionary; do not add a plugin loader.
- [ ] Run focused tests; expect all to pass.
- [ ] Commit with `feat: add typed tool calling contracts`.

### Task 3: Cited PDF RAG

**Files:**

- Create: rag/__init__.py
- Create: rag/pdf_loader.py
- Create: rag/chunking.py
- Create: rag/index.py
- Create: rag/retriever.py
- Create: tests/fixtures/knowledge/sample_manual.pdf
- Create: tests/rag/test_pdf_loader.py
- Create: tests/rag/test_chunking.py
- Create: tests/rag/test_index.py
- Create: tests/rag/test_retriever.py

**Interfaces:**

- Produce load_pdf(path) returning page-aware source documents.
- Produce split_documents(documents, chunk_size, overlap) returning stable chunk identifiers.
- Produce index_pdf(path, collection, embedder) returning inserted and unchanged counts.
- Produce retrieve(query, collection, embedder, top_k, score_threshold) returning RetrievedChunk records.

- [ ] Write deterministic tests for page metadata, code and hexadecimal token preservation, overlap, stable identifiers, idempotent indexing, ranking, empty results, and citation fields.
- [ ] Run `pytest tests/rag -q`; expect import failures.
- [ ] Implement parsing with PyMuPDF, simple paragraph-aware chunking, direct Chroma access, and one injectable embedding callable.
- [ ] Run RAG tests twice against a temporary Chroma directory; expect identical pass results and no duplicate chunks.
- [ ] Commit with `feat: add cited PDF retrieval pipeline`.

### Task 4: Agent State and Supervisor Routing

**Files:**

- Create: agents/__init__.py
- Create: agents/state.py
- Create: agents/supervisor.py
- Create: tests/agents/test_supervisor.py

**Interfaces:**

- Produce Route values knowledge, firmware, and debug.
- Produce AgentState containing request, route, routing_reason, messages, retrieved_chunks, tool_results, errors, and response.
- Produce route_request(state, model) returning only route and routing_reason updates.

- [ ] Write tests for knowledge lookup, firmware generation or review, debug or log analysis, and invalid model routing output.
- [ ] Run `pytest tests/agents/test_supervisor.py -q`; expect import failure.
- [ ] Implement constrained routing with a typed model response and a deterministic invalid-output error.
- [ ] Run focused tests; expect all to pass without a live model.
- [ ] Commit with `feat: add supervisor routing and agent state`.

### Task 5: Knowledge, Firmware, and Debug Agents

**Files:**

- Create: agents/knowledge.py
- Create: agents/firmware.py
- Create: agents/debug.py
- Create: tests/agents/test_knowledge.py
- Create: tests/agents/test_firmware.py
- Create: tests/agents/test_debug.py

**Interfaces:**

- Produce answer_knowledge(state, model, retriever).
- Produce answer_firmware(state, model, retriever, tools).
- Produce answer_debug(state, model, retriever, tools).
- Each function returns a partial AgentState update and never mutates the input.

- [ ] Write Knowledge tests for citations, insufficient context, and retriever errors.
- [ ] Write Firmware tests for cited assumptions, embedded-domain constraints, and tool failure.
- [ ] Write Debug tests for observed, cited, inferred, and assumed evidence labels.
- [ ] Run `pytest tests/agents/test_knowledge.py tests/agents/test_firmware.py tests/agents/test_debug.py -q`; expect import failures.
- [ ] Implement the three smallest specialist nodes using injected callables and shared contracts.
- [ ] Run focused tests; expect all to pass.
- [ ] Commit with `feat: add specialist agents`.

### Task 6: LangGraph Workflow

**Files:**

- Create: agents/workflow.py
- Create: tests/agents/test_workflow.py

**Interfaces:**

- Produce build_workflow(model, retriever, tools) returning a compiled graph.
- Produce invoke(request) returning CopilotResponse.
- Graph edges are start to Supervisor, Supervisor to exactly one specialist, then end.

- [ ] Write tests for every route, citation propagation, specialist errors, invalid state, and one terminal completion per request.
- [ ] Run `pytest tests/agents/test_workflow.py -q`; expect import failure.
- [ ] Implement the smallest acyclic LangGraph; do not add retries until a measured failure requires them.
- [ ] Run all agent and workflow tests; expect all to pass.
- [ ] Commit with `feat: orchestrate agents with LangGraph`.

### Task 7: FastAPI Boundary

**Files:**

- Create: api/__init__.py
- Create: api/main.py
- Create: api/schemas.py
- Create: api/routes.py
- Create: api/errors.py
- Create: tests/api/test_health.py
- Create: tests/api/test_query.py

**Interfaces:**

- Produce GET /api/v1/health returning status and version.
- Produce POST /api/v1/query accepting query and optional conversation_id.
- Return answer, route, citations, and trace_id.
- Map validation, retrieval, tool, timeout, and internal failures to stable error codes.

- [ ] Write API tests for health, valid queries, citations, validation errors, workflow errors, and trace identifiers.
- [ ] Run `pytest tests/api -q`; expect import failure.
- [ ] Implement app lifespan, dependencies, routes, schemas, error handlers, and structured request logs.
- [ ] Run API tests; expect all to pass with a fake workflow.
- [ ] Commit with `feat: expose Embedded Copilot FastAPI endpoints`.

### Task 8: Full Verification and v0.1.0 Release Readiness

**Files:**

- Create: README.md
- Create: tests/test_package_version.py
- Modify: pyproject.toml

**Interfaces:**

- Document local setup, PDF ingestion, API startup, test commands, limitations, and citation behavior.
- Expose package version 0.1.0 and prepare Git tag v0.1.0 only after approval.

- [ ] Add a test that package, API health, and documented version values are all 0.1.0.
- [ ] Run `pytest -q`; expect the complete offline suite to pass.
- [ ] Run `ruff check .` and `mypy agents rag tools api core models`; expect no errors.
- [ ] Run the API locally and verify health plus one fake-backed query.
- [ ] Perform requesting-code-review and resolve findings.
- [ ] Perform verification-before-completion and record exact command results.
- [ ] Commit with `docs: document v0.1.0 usage and verification`.
- [ ] After explicit release approval, create annotated tag v0.1.0.

## Approval Checkpoint

Do not execute Task 1 until the user confirms this plan and the recommended directory structure.
