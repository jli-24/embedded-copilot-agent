# Embedded Copilot Agent v0.1.0 Development Roadmap

> **Approval artifact:** This roadmap fixes scope, architecture, milestones, interfaces, acceptance criteria, and commit boundaries. It is not passed directly to executing-plans. After approval, create the four execution-grade plans listed under Execution Plan Decomposition; each must contain exact failing-test code, 2–5-minute steps, commands, and expected output.

**Goal:** Deliver an offline-testable Embedded Copilot Agent v0.1.0 with four LangGraph agents, cited PDF RAG, typed Tool Calling, and a FastAPI query interface.

**Architecture:** A small LangGraph workflow routes a typed request from Supervisor to one specialist. Knowledge uses the RAG retriever; Firmware and Debug may use retrieved context and registered tools. FastAPI is a thin boundary over the workflow. Production composition uses configurable OpenAI-compatible chat and embedding adapters. Tests use deterministic model and embedding fakes, temporary Chroma collections, and fake device tools.

**Tech Stack:** Python 3.12, LangGraph, FastAPI, Pydantic v2, ChromaDB, PyMuPDF, langchain-openai, pytest, HTTPX, Ruff, mypy.

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
- adapters/openai.py: configurable production chat and embedding adapters.
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
- api/dependencies.py: production composition root for settings, adapters, Chroma, tools, and workflow.
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

- Produce Settings with app_name, version, log_level, chroma_path, collection_name, embedding_model, chat_model, openai_base_url, openai_api_key, chunk_size, chunk_overlap, retrieval_top_k, retrieval_score_threshold, and request_timeout_seconds.

- [ ] Write tests named test_settings_defaults, test_chunk_overlap_must_be_smaller_than_chunk_size, test_retrieval_values_are_bounded, and test_api_key_is_secret.
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

- [ ] Write deterministic tests named test_loader_keeps_page_metadata, test_chunker_preserves_code_tokens, test_chunk_ids_are_stable, test_index_is_idempotent, test_retriever_applies_threshold, and test_retriever_returns_citations.
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

- [ ] Write tests named test_routes_knowledge_request, test_routes_firmware_request, test_routes_debug_request, and test_rejects_invalid_route.
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

- [ ] Write Knowledge tests named test_knowledge_preserves_citations, test_knowledge_reports_insufficient_context, and test_knowledge_maps_retriever_error.
- [ ] Write Firmware tests named test_firmware_labels_assumptions, test_firmware_preserves_sources, and test_firmware_maps_tool_error.
- [ ] Write Debug tests named test_debug_labels_evidence and test_debug_does_not_promote_inference_to_observation.
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

- [ ] Write tests named test_workflow_reaches_each_specialist, test_workflow_propagates_citations, test_workflow_terminates_on_specialist_error, and test_workflow_completes_once.
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

- [ ] Write API tests named test_health_reports_v010, test_query_returns_citations, test_query_rejects_blank_input, test_query_maps_workflow_error, and test_query_returns_trace_id.
- [ ] Run `pytest tests/api -q`; expect import failure.
- [ ] Implement app lifespan, dependencies, routes, schemas, error handlers, and structured request logs.
- [ ] Run API tests; expect all to pass with a fake workflow.
- [ ] Commit with `feat: expose Embedded Copilot FastAPI endpoints`.

### Task 8: Production Adapters and Composition

**Files:**

- Create: adapters/__init__.py
- Create: adapters/openai.py
- Create: api/dependencies.py
- Create: tests/adapters/test_openai.py
- Create: tests/api/test_dependencies.py

**Interfaces:**

- Produce OpenAIChatAdapter(settings) with the typed chat interface consumed by agents.
- Produce OpenAIEmbeddingAdapter(settings) with embed_documents and embed_query.
- Produce build_application(settings) that composes adapters, Chroma collection, tool registry, retriever, workflow, and FastAPI dependencies.

- [ ] Write tests named test_chat_adapter_uses_configured_model, test_embedding_adapter_uses_configured_model, test_secret_is_not_logged, and test_build_application_wires_real_adapters.
- [ ] Run `pytest tests/adapters/test_openai.py tests/api/test_dependencies.py -q`; expect import failure.
- [ ] Implement the two thin langchain-openai adapters and one composition function; do not add a provider factory or second provider.
- [ ] Run focused adapter and dependency tests; expect all to pass without network calls.
- [ ] Commit with `feat: compose production model and embedding adapters`.

### Task 9: Full Verification and v0.1.0 Release Readiness

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
- [ ] Run the API locally and verify health plus one deterministic offline query through the production composition with patched external clients.
- [ ] When approved credentials are available, run one optional live chat-and-embedding smoke test and record the model identifiers; absence of credentials does not invalidate the offline suite.
- [ ] Perform requesting-code-review and resolve findings.
- [ ] Perform verification-before-completion and record exact command results.
- [ ] Commit with `docs: document v0.1.0 usage and verification`.
- [ ] After explicit release approval, create annotated tag v0.1.0.

## Approval Checkpoint

Do not execute Task 1 until the user confirms this plan and the recommended directory structure.

## Execution Plan Decomposition

After approval, use writing-plans to produce these separate executable plans before implementation:

1. docs/superpowers/plans/2026-07-20-foundation-tools-execution.md for Tasks 1–2.
2. docs/superpowers/plans/2026-07-20-rag-execution.md for Task 3.
3. docs/superpowers/plans/2026-07-20-agents-workflow-execution.md for Tasks 4–6.
4. docs/superpowers/plans/2026-07-20-api-runtime-release-execution.md for Tasks 7–9.

Each execution plan must show complete failing-test code, minimal implementation code, exact commands, expected failure and pass output, and one reviewable commit per task. Do not invoke executing-plans with this roadmap.
