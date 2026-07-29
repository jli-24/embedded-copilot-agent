# Embedded Copilot v0.40.0 Memory-aware Engineering Intelligence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic, verified-only Engineering Memory retrieval and memory-aware planning without changing the v0.39 Memory trust model or write boundary.

**Architecture:** `EngineeringMemoryRetriever` reads the existing verified snapshot and revision-bound history exclusively through `EngineeringMemoryPort`, correlates them into an immutable read-side view, applies fixed integer ranking, and returns a fingerprinted `MemoryContext`. The existing Supervisor optionally fuses that context with `KnowledgeContext` in `EngineeringPlanningContext`, then projects only domain-compatible records to each Domain Agent; every Memory failure safely falls back without blocking the Agent workflow.

**Tech Stack:** Python 3.11, Pydantic strict frozen models, `typing.Protocol`, deterministic SHA-256 serialization, pytest, Ruff, Black 26.5.1, compileall, pip check, and Git staged-tree validation.

## Global Constraints

- This document is an implementation plan. It does not represent completed v0.40 production or test code.
- v0.40 is a read-side enhancement, not a Memory model rewrite.
- Do not modify the existing `EngineeringMemoryStorePort`, `EngineeringMemoryPort`, Permission contracts, Audit contracts, or Verification contracts.
- Do not add fields to v0.39 `EngineeringMemoryRecord`, `MemorySnapshotRecord`, `EngineeringMemorySnapshot`, `VerificationEvidenceBinding`, authorization DTOs, or audit events.
- The Retriever may depend only on the public `EngineeringMemoryPort` and public frozen contracts.
- The Retriever may construct only `GetVerifiedSnapshotRequest` and `GetHistoryRequest`; it must never construct or dispatch a mutation command.
- Existing `EngineeringMemoryPort.execute()` calls remain the only route to v0.39 Permission and Audit processing. Do not add a second Permission or Audit system.
- All new public DTOs use `frozen=True`, `extra="forbid"`, `revalidate_instances="always"`, strict validation, tuple collections, UTC-aware timestamps, and deterministic serialization.
- Runtime code must not read a clock, generate UUIDs, use random values, or maintain mutable module-level usage state.
- Retrieval must not update usage, Memory records, aggregate revision, receipts, audit schemas, or Supervisor trace content.
- Only VERIFIED records may enter `MemoryContext`; every inconsistent state, binding, revision, timestamp, or identity causes the whole retrieval to fail closed.
- No partial context is returned after a malformed page, dependency failure, input mutation, Permission denial, or Audit failure.
- Human Approval is an engineering acceptance basis, not technical Verification. Its ranking verification factor is `0`, evidence confidence is `0.5`, and `verification_confidence` is `None`.
- Verification-backed evidence requires a final `VERIFICATION` transition and final associated `PASS` binding; its ranking verification factor is `1000` and evidence confidence is `1.0`.
- `FAIL` never means a confirmed hardware fault; failed or review-required Verification evidence is not eligible for verified retrieval.
- Knowledge and Memory remain separate sources with separate provenance and fingerprints. Fusion must not replace, merge, or silently choose between them.
- Memory enrichment is optional. Missing binding, empty results, Permission denial, Audit failure, Store failure, invalid read results, and Retriever failure must not stop the existing Agent workflow.
- Do not add Web Search, Browser Agent, vector retrieval, embedding, autonomous learning, persistent database, cache, background worker, filesystem, network, environment, Workspace mutation, Git, Shell, subprocess, build, device, serial, or hardware operations.
- Workspace Runtime remains the only engineering-file write boundary.
- Do not add API, UI, Streamlit, or VS Code command integration in this release.
- Use TDD: record the named RED failure, implement the smallest approved behavior, run the named GREEN gate, and review the task diff before proceeding.
- Do not create intermediate implementation commits. The present documentation delivery creates only the documentation commit defined in Task 15.
- Any failed focused, security, regression, release, quality, cached-diff, or tree-integrity gate stops execution without a release claim.

---

## Execution Preflight for Future Implementation

Before Task 1, use an existing Python environment and run:

```powershell
python --version
python -c "import pytest, pydantic, embedded_copilot; print('imports OK')"
python -m black --version
python -m ruff --version
python -m pip check
```

Python must be 3.11.x, Black must be exactly 26.5.1, Ruff must execute as a CLI, and the existing project dependencies must import successfully. Do not install, upgrade, repair, or modify dependencies. Stop before Task 1 if the environment fails this preflight.

Record the implementation branch, base commit, tag state, empty index, and existing dirty files. Future implementation must occur in its own worktree derived from the approved design-and-plan history, never in the dirty main checkout.

## File Responsibility Map

### Production files

- `src/embedded_copilot/engineering_memory/context.py`: define the strict read-side enums and DTOs, canonical serialization, context alignment validation, and context fingerprint. Consumes existing public Memory and Verification enums; produces every public Retrieval/Memory Context contract except `EngineeringPlanningContext`.
- `src/embedded_copilot/engineering_memory/ranking.py`: provide pure domain mapping, trust projection, factor normalization, score calculation, and stable ordering. Consumes correlated immutable records plus usage signals; produces ranked internal candidates and `MemoryRankingBreakdown`.
- `src/embedded_copilot/engineering_memory/retrieval.py`: validate the factory dependency, isolate inputs, derive deterministic child request IDs, execute verified snapshot/history reads, correlate the read-side view, rank candidates, and revalidate `MemoryContext`. Consumes `EngineeringMemoryPort`; produces `create_engineering_memory_retriever()` and `EngineeringMemoryRetriever`.
- `src/embedded_copilot/engineering_memory/exceptions.py`: add the three sanitized public Retrieval exceptions without changing v0.39 exception meanings.
- `src/embedded_copilot/engineering_memory/__init__.py`: append only the approved read-side public exports; preserve every v0.39 export and export order contract.
- `src/embedded_copilot/agents/types.py`: add optional `memory_binding: MemoryRetrievalBinding | None = None` to `AgentTask` and isolate/revalidate it. Existing callers remain valid.
- `src/embedded_copilot/services/analysis.py`: add the same optional binding to `AnalysisCommand`, revalidate it in `__post_init__`, preserve it across queue isolation, and pass it into `AgentTask`. Do not expose it through an API schema in v0.40.
- `src/embedded_copilot/supervisor/context.py`: define `EngineeringPlanningContext`, its fusion fingerprint, optional Knowledge/Memory fields, and safe trace stages while preserving existing context behavior.
- `src/embedded_copilot/supervisor/memory_adapters.py`: project a revalidated `MemoryContext` to one Domain Agent, retaining matching or GENERAL records and aligned evidence only.
- `src/embedded_copilot/supervisor/agent.py`: inject an optional Retriever and execute analysis, retrieval/fallback, knowledge lookup, fusion, planning, and dispatch in the approved order.
- `src/embedded_copilot/supervisor/planner.py`: accept an optional `EngineeringPlanningContext`, preserve the current call shape through a default, and add only safe Memory identity/ranking data to deterministic invocations.
- `src/embedded_copilot/supervisor/dispatcher.py`: attach the per-domain projection to Agent metadata without exposing Retriever, MemoryPort, Store, Permission, Audit, or full history objects.

Do not create `src/embedded_copilot/agents/memory_supervisor.py`. The existing `SupervisorAgent` is the single orchestration path.

### Test files

- `tests/engineering_memory/test_retrieval_contracts.py`: strict DTOs, enum values, UTC, sorting, nested-instance revalidation, factory, facade, and exports.
- `tests/engineering_memory/test_read_projection.py`: snapshot/history correlation, pagination, aggregate revision binding, identity checks, trust basis, and future timestamps.
- `tests/engineering_memory/test_retrieval.py`: child IDs, query sequence, verified-only reads, input isolation, output validation, limits, empty context, and no partial delivery.
- `tests/engineering_memory/test_domain_mapping.py`: all eight payload mappings, PASS-subject precedence, provenance fallback, GENERAL behavior, and incompatible filtering.
- `tests/engineering_memory/test_ranking.py`: four factor boundaries, 40/30/20/10 formula, three-decimal score, usage cap, recency buckets, and caller signal validation.
- `tests/engineering_memory/test_deterministic_ranking.py`: complete tie-break order, repeated-call stability, limit behavior, and permutation independence.
- `tests/engineering_memory/test_memory_context.py`: record/evidence alignment, confidence semantics, immutable output, canonical serialization, and fingerprint tamper rejection.
- `tests/supervisor/test_memory_fusion.py`: Knowledge-only, Memory-only, combined, both-empty contexts, conflict preservation, and fusion fingerprint.
- `tests/supervisor/test_memory_integration.py`: optional injection, execution order, typed request construction, planning consumption, and existing `run(task)` compatibility.
- `tests/supervisor/test_memory_fallback.py`: the six-row Failure Matrix, continued dispatch, and content-free trace assertions.
- `tests/supervisor/test_memory_dispatch.py`: FIRMWARE/HARDWARE/PCB/DEBUG/GENERAL projection, deep-copy isolation, and forbidden object absence.
- `tests/services/test_analysis.py`: optional binding validation, queue isolation, propagation, and default compatibility.
- `tests/security/test_memory_intelligence_boundary.py`: fixed package files, AST import/call/token gates, read-only command allowlist, no mutable global state, and narrow exports.
- `tests/security/test_engineering_memory_boundary.py`: regression for the unchanged eight-method Store Port, single-method MemoryPort, nine-field Permission request, Audit schema, and Verification contracts.
- `tests/release/test_v040_release.py`: version synchronization, release documentation, dependency stability, non-goals, and quality-gate contract.
- Existing Supervisor, Engineering Memory, Verification Agent, Workspace Runtime, Tool Runtime, release compatibility, and release metadata tests remain regression gates rather than being duplicated.

## Locked Public Contracts

```python
def create_engineering_memory_retriever(
    *,
    memory_port: EngineeringMemoryPort,
) -> EngineeringMemoryRetriever: ...


class EngineeringMemoryRetriever:
    def retrieve(
        self,
        request: MemoryRetrievalRequest,
    ) -> MemoryContext: ...
```

The new contracts have these exact fields:

- `MemoryUsageSignal(record_id, usage_count)` where `usage_count` is a strict non-negative integer.
- `MemoryRetrievalBinding(request_id, project_id, memory_id, caller, requested_at, usage_signals=(), limit=8)`.
- `MemoryRetrievalRequest` contains every binding field plus non-empty `domains`.
- `MemoryDomain`: `FIRMWARE`, `HARDWARE`, `PCB`, `DEBUG`, `GENERAL`.
- `MemoryTrustBasis`: `VERIFICATION`, `HUMAN_APPROVAL`.
- `MemoryRankingBreakdown(verification_millis, domain_millis, usage_millis, recency_millis, total_millis, relevance_score)`.
- `MemoryContextEvidence(record_id, memory_type, logical_key, trust_basis, verification_subject, verification_confidence, provenance_source_type, provenance_reference, last_transition_at, ranking)`.
- `MemoryContext(request_id, project_id, memory_id, aggregate_revision, domains, records, evidence, confidence, source_snapshot_fingerprint, context_fingerprint)`.
- `EngineeringPlanningContext(task, knowledge_context, memory_context, selected_domains, fusion_fingerprint)` where `task` is a revalidated `SupervisorTask`.

The following signatures and schemas remain byte-for-byte compatible at the public contract level:

```python
class EngineeringMemoryPort(Protocol):
    def execute(
        self,
        request: EngineeringMemoryRequest,
    ) -> EngineeringMemoryResult: ...


class MemoryPermissionPort(Protocol):
    def authorize(
        self,
        request: MemoryAuthorizationRequest,
    ) -> MemoryPermissionDecision: ...


class MemoryAuditSink(Protocol):
    def record(self, event: MemoryAuditEvent) -> None: ...
```

`EngineeringMemoryStorePort` remains the existing five mutation plus three query methods. Retrieval must not import or call it.

---

### Task 1: Strict Contract Foundation

**Files:**
- Create: `src/embedded_copilot/engineering_memory/context.py`
- Modify: `src/embedded_copilot/engineering_memory/exceptions.py`
- Test: `tests/engineering_memory/test_retrieval_contracts.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel`, `ConfigDict`, `Field`, validators; existing `MemoryType`, `MemorySourceType`, `MemorySnapshotRecord`, and `VerificationSubjectType`.
- Produces: strict base contract, `MemoryDomain`, `MemoryTrustBasis`, all Retrieval/Memory Context DTOs, `MemoryRetrievalError`, `MemoryRetrievalRequestRejected`, and `MemoryRetrievalUnavailable`.

- [ ] **Step 1: Write RED contract tests.** Define named tests `test_retrieval_contracts_are_frozen_strict_and_forbid_extra`, `test_retrieval_binding_requires_utc_and_stable_usage_signals`, `test_retrieval_request_requires_unique_sorted_domains`, `test_bool_is_not_a_usage_count`, and `test_nested_instances_are_revalidated_after_tampering`. Assert the exact field order listed in Locked Public Contracts.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/engineering_memory/test_retrieval_contracts.py -q
  ```

  Expected: collection fails because the read-side types do not exist. Any unrelated failure is not accepted as RED evidence.
- [ ] **Step 3: Implement the minimum contracts.** Use one private strict frozen base, normalize aware timestamps to UTC, reject unknown/duplicate usage IDs, sort usage signals by `record_id`, sort domains by enum value, enforce limit `1..50`, enforce `0..1000` integer factors, and reject non-finite or inconsistent score values. Add only sanitized fixed-message exception classes.
- [ ] **Step 4: Run GREEN.** Run the Task 1 test file and existing `tests/engineering_memory/test_contracts.py`; both must pass.
- [ ] **Step 5: Review.** Run `git diff --check` and review only Task 1 files. Confirm no v0.39 DTO or exception behavior changed.

**Completion condition:** All new base contracts reject extra/coerced/tampered input, and existing Engineering Memory contract tests remain green.

### Task 2: Verified Memory Read Projection

**Files:**
- Create: `tests/engineering_memory/test_read_projection.py`
- Modify: `src/embedded_copilot/engineering_memory/retrieval.py`
- Test: `tests/engineering_memory/test_read_projection.py`

**Interfaces:**
- Consumes: existing `EngineeringMemorySnapshot`, `EngineeringMemoryHistoryPage`, `EngineeringMemoryRecord`, state transitions, Verification bindings, and Human Approval binding.
- Produces: private immutable correlated candidate records containing an unchanged snapshot record plus derived domains, trust basis, verification subject/projection, evidence confidence, and `last_transition_at`.

- [ ] **Step 1: Write RED projection tests.** Cover one-to-one record correlation, payload/provenance/status/revision/logical-key/type equality, duplicate/missing history records, snapshot/history revision mismatch, non-VERIFIED history status, future transition time, invalid final transition, PASS binding mismatch, and Human Approval-only projection.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/engineering_memory/test_read_projection.py -q
  ```

  Expected: import fails for the private correlation behavior or assertions fail because no projection exists.
- [ ] **Step 3: Implement the minimum correlation algorithm.** Revalidate deep copies of both results, index history records by unique `record_id`, compare every snapshot field, require matching aggregate revisions, require VERIFIED status on both sides, inspect only the final transition and associated binding, and reject the entire view on the first inconsistency. Do not extend any existing v0.39 DTO. Set PASS-path projected verification confidence to `1.0`; set Human Approval verification subject/confidence to `None` and evidence completeness to `0.5`.
- [ ] **Step 4: Run GREEN.** Run the new projection tests plus `tests/engineering_memory/test_queries.py` and `tests/engineering_memory/test_state_transitions.py`.
- [ ] **Step 5: Review.** Inspect `git diff -- src/embedded_copilot/engineering_memory tests/engineering_memory` and confirm no Snapshot, Record, binding, Store, Permission, or Audit field changed.

**Completion condition:** Existing read results can be correlated deterministically without changing v0.39 public contracts, and no inconsistent view produces a partial candidate set.

### Task 3: Memory Retrieval Request Pipeline

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/retrieval.py`
- Modify: `src/embedded_copilot/engineering_memory/__init__.py`
- Create: `tests/engineering_memory/test_retrieval.py`
- Modify: `tests/engineering_memory/test_retrieval_contracts.py`

**Interfaces:**
- Consumes: `EngineeringMemoryPort.execute()`, `GetVerifiedSnapshotRequest`, `GetHistoryRequest`, Task 1 requests, and Task 2 correlation.
- Produces: `create_engineering_memory_retriever(*, memory_port)`, `EngineeringMemoryRetriever.retrieve(request)`, deterministic child request IDs, and approved exports.

- [ ] **Step 1: Write RED pipeline tests.** Name tests for invalid/missing/asynchronous ports, facade narrowness, request input mutation, fixed snapshot-first call order, revision-bound history pagination, child request replay stability, per-page child ID uniqueness, Permission/Audit/Store exception sanitation, unexpected result type, empty aggregate, limit handling, and no partial delivery.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/engineering_memory/test_retrieval.py tests/engineering_memory/test_retrieval_contracts.py -q
  ```

  Expected: factory/retriever imports fail and no queries are issued.
- [ ] **Step 3: Implement the minimum pipeline.** Validate the runtime-checkable synchronous port, deep-copy/revalidate the request, derive `mr-` plus the first 32 lowercase SHA-256 hex characters from canonical request + stage + page, execute one verified snapshot query, then page history with the returned revision-bound cursor until `has_more=False`. Check every returned request/project/memory identity and aggregate revision. Convert request validation faults to `MemoryRetrievalRequestRejected`; convert dependency/result faults to `MemoryRetrievalUnavailable` with a fixed safe message.
- [ ] **Step 4: Run GREEN.** Run the two new test files and existing Permission/Audit/query tests.
- [ ] **Step 5: Review.** Use `git diff --check`, inspect exports, and AST-search retrieval code to confirm it constructs only the two allowed query requests.

**Completion condition:** The public Retriever is synchronous, deterministic, input-isolated, permission/audit-preserving, and never returns partial data.

### Task 4: Domain Mapping

**Files:**
- Create: `src/embedded_copilot/engineering_memory/ranking.py`
- Create: `tests/engineering_memory/test_domain_mapping.py`

**Interfaces:**
- Consumes: correlated candidate records, `MemoryType`, payload discriminators, `MemorySourceType`, final PASS subject, and `MemoryDomain`.
- Produces: a pure internal `record_domains(candidate) -> tuple[MemoryDomain, ...]` mapping and domain relevance factor.

- [ ] **Step 1: Write RED mapping tests.** Cover Board/Component/Pin/Interface/Power to HARDWARE+PCB; Verification History FIRMWARE/HARDWARE/TOOL_RESULT mapping; Decision/Issue PASS-subject precedence; CODING, DEBUG, TELEMETRY, DATASHEET, and GENERAL provenance fallback; exact match `1000`; GENERAL `500`; incompatible filtering.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/engineering_memory/test_domain_mapping.py -q
  ```

  Expected: mapping imports fail.
- [ ] **Step 3: Implement the fixed mapping table.** Use enum/discriminator comparisons only. Return stable enum-sorted tuples, prefer final PASS subject for Decision/Issue, and use provenance only when that PASS subject is absent. Never inspect free text.
- [ ] **Step 4: Run GREEN.** Run the mapping tests and payload contract regression.
- [ ] **Step 5: Review.** Confirm every one of the eight Memory payload types has an explicit branch and no model, embedding, keyword, or mutable registry is present.

**Completion condition:** Domain mapping exactly matches design section 7 and produces stable filtering factors.

### Task 5: Memory Ranking Engine

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/ranking.py`
- Create: `tests/engineering_memory/test_ranking.py`

**Interfaces:**
- Consumes: Task 4 domain result, trust basis, caller-owned `MemoryUsageSignal`, `requested_at`, and `last_transition_at`.
- Produces: validated `MemoryRankingBreakdown` and an internal ranked candidate.

- [ ] **Step 1: Write RED factor tests.** Cover Verification `1000/0`, domain `1000/500/filter`, usage counts `0/1/19/20/>20`, bool rejection, missing signal, recency exactly 30/180/365 days and one microsecond over each boundary, greater than 365 days, future transition rejection, and the exact weighted formula.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/engineering_memory/test_ranking.py -q
  ```

  Expected: factor and scoring functions are absent.
- [ ] **Step 3: Implement integer-only scoring.** Compute `usage_millis=min(usage_count, 20) * 50`; use recency buckets `1000/750/500/250`; compute `(4*verification + 3*domain + 2*usage + recency)//10`; derive `relevance_score=total_millis/1000` and validate its deterministic three-decimal representation. Reject future timestamps before scoring.
- [ ] **Step 4: Run GREEN.** Run ranking, domain mapping, and contract tests.
- [ ] **Step 5: Review.** Confirm no float arithmetic participates in ordering and no caller-adjustable weights exist.

**Completion condition:** Every factor boundary and the 40/30/20/10 total match the locked formula exactly.

### Task 6: Deterministic Ranking

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/ranking.py`
- Create: `tests/engineering_memory/test_deterministic_ranking.py`
- Modify: `src/embedded_copilot/engineering_memory/retrieval.py`

**Interfaces:**
- Consumes: Task 5 ranked candidates and request limit.
- Produces: stable ranked candidate tuples independent of input iteration order.

- [ ] **Step 1: Write RED ordering tests.** Isolate each tie-break level in order: total, verification, domain, usage, recency descending, then `memory_type.value`, `logical_key`, and `record_id` ascending. Permute the input candidates and repeat retrieval to prove byte-stable ordering. Cover limits 1, default 8, and 50.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/engineering_memory/test_deterministic_ranking.py -q
  ```

  Expected: ordering assertions fail because the stable sort key is not implemented.
- [ ] **Step 3: Implement the exact sort key.** Sort by `(-total_millis, -verification_millis, -domain_millis, -usage_millis, -recency_millis, memory_type.value, logical_key, record_id)` and apply limit only after complete filtering and sorting.
- [ ] **Step 4: Run GREEN.** Run deterministic ranking and all ranking/mapping tests.
- [ ] **Step 5: Review.** Verify no set/dict iteration order reaches output and limit never affects factor calculation.

**Completion condition:** Equivalent inputs always produce the same ordered record IDs and ranking breakdowns.

### Task 7: Memory Context Contract

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/context.py`
- Modify: `src/embedded_copilot/engineering_memory/retrieval.py`
- Create: `tests/engineering_memory/test_memory_context.py`

**Interfaces:**
- Consumes: ranked candidates, request identity, aggregate revision, source snapshot fingerprint, and selected domains.
- Produces: final `MemoryContext`, aligned evidence, context confidence, and canonical `context_fingerprint`.

- [ ] **Step 1: Write RED context tests.** Cover records/evidence length and record-ID alignment, uniqueness, limit, domain binding, non-empty confidence minimum, empty confidence `0.0`, empty tuple shape, aggregate/source fingerprint preservation, frozen output, nested tamper rejection, field-order-independent construction, repeated fingerprint stability, and fingerprint mismatch rejection.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/engineering_memory/test_memory_context.py -q
  ```

  Expected: context construction/fingerprint assertions fail.
- [ ] **Step 3: Implement canonical context construction.** Revalidate every selected snapshot record, build evidence in identical order, use `1.0` or `0.5` evidence completeness, calculate context confidence as the minimum or `0.0`, serialize all fields except `context_fingerprint` using stable JSON keys, compact separators, UTF-8, and `allow_nan=False`, then prefix the lowercase SHA-256 digest with `sha256:`.
- [ ] **Step 4: Run GREEN.** Run context, retrieval, projection, and ranking tests.
- [ ] **Step 5: Review.** Confirm evidence excludes Finding, Approval body, state history, logs, paths, secrets, and exception text.

**Completion condition:** `MemoryContext` is immutable, internally aligned, deterministically fingerprinted, and contains only approved evidence.

### Task 8: Knowledge Gateway Fusion

**Files:**
- Modify: `src/embedded_copilot/supervisor/context.py`
- Create: `tests/supervisor/test_memory_fusion.py`

**Interfaces:**
- Consumes: revalidated `SupervisorTask`, optional existing `KnowledgeContext`, optional `MemoryContext`, and selected domains.
- Produces: `EngineeringPlanningContext` and deterministic `fusion_fingerprint`.

- [ ] **Step 1: Write RED fusion tests.** Cover Knowledge-only, Memory-only, combined, both absent, queried-empty Memory, source conflict preservation, tuple/domain ordering, nested mutation isolation, and fingerprint stability/tamper rejection.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/supervisor/test_memory_fusion.py -q
  ```

  Expected: `EngineeringPlanningContext` is unavailable.
- [ ] **Step 3: Implement the fusion contract.** Keep `knowledge_context` and `memory_context` as independent optional fields; do not deduplicate or overwrite either. Fingerprint the revalidated task identity, selected domains, Knowledge projection, and Memory projection with canonical SHA-256. Keep existing `KnowledgeContext` semantics intact.
- [ ] **Step 4: Run GREEN.** Run the new fusion tests and existing Supervisor context/gateway tests.
- [ ] **Step 5: Review.** Verify fusion performs no Memory write, winner selection, replacement creation, or provenance collapse.

**Completion condition:** All four source-presence combinations produce a valid deterministic planning context without changing Knowledge Gateway behavior.

### Task 9: Supervisor Integration

**Files:**
- Modify: `src/embedded_copilot/agents/types.py`
- Modify: `src/embedded_copilot/services/analysis.py`
- Modify: `src/embedded_copilot/supervisor/agent.py`
- Modify: `src/embedded_copilot/supervisor/planner.py`
- Create: `src/embedded_copilot/supervisor/memory_adapters.py`
- Modify: `src/embedded_copilot/supervisor/dispatcher.py`
- Create: `tests/supervisor/test_memory_integration.py`
- Create: `tests/supervisor/test_memory_dispatch.py`
- Modify: `tests/services/test_analysis.py`

**Interfaces:**
- Consumes: optional `MemoryRetrievalBinding`, `EngineeringMemoryRetriever`, Task 8 planning context, current Analyzer/Knowledge Gateway/Planner/Dispatcher contracts.
- Produces: backward-compatible `AgentTask` and `AnalysisCommand`, optional Retriever injection, safe per-Agent Memory metadata, and the fixed analysis-to-dispatch sequence.

- [ ] **Step 1: Write RED integration tests.** Verify default `None` compatibility, AnalysisCommand queue isolation, binding propagation, no Retriever call without binding, domains derived from selected agents, retrieval before fusion/planning, empty context retained, `run(task)` signature unchanged, Planner optional-context compatibility, and per-domain delivery of matching or GENERAL records only.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/supervisor/test_memory_integration.py tests/supervisor/test_memory_dispatch.py tests/services/test_analysis.py -q
  ```

  Expected: optional binding and Retriever injection are unsupported.
- [ ] **Step 3: Implement the minimum integration.** Add the optional binding with deep-copy revalidation; pass it through AnalysisService; inject `memory_retriever: EngineeringMemoryRetriever | None = None` into the existing Supervisor; derive stable domains from selected Agents; retrieve before Knowledge/fusion/planning; pass `EngineeringPlanningContext` to Planner through an optional keyword; use `project_memory_context(agent_name, context)` to emit only aligned domain records/evidence under one safe `memory_context` metadata key. Do not add a second Supervisor class or change the public `run(task)` method.
- [ ] **Step 4: Run GREEN.** Run the new tests plus all existing `tests/supervisor`, `tests/agents`, `tests/services/test_analysis.py`, and `tests/integration/test_supervisor_integration.py`.
- [ ] **Step 5: Review.** Confirm Domain Agents receive no Retriever, MemoryPort, Store, Permission, Audit, history page, state history, or exception object.

**Completion condition:** Existing callers behave unchanged by default, while a trusted typed binding activates deterministic Memory retrieval and domain projection.

### Task 10: Fallback and Failure Handling

**Files:**
- Modify: `src/embedded_copilot/supervisor/agent.py`
- Modify: `src/embedded_copilot/supervisor/context.py`
- Create: `tests/supervisor/test_memory_fallback.py`

**Interfaces:**
- Consumes: Retrieval exceptions, malformed injected results, current Supervisor trace and Agent dispatch.
- Produces: content-free `memory_retrieved`, `memory_fallback`, and `context_fused` trace stages plus safe continued execution.

- [ ] **Step 1: Write RED Failure Matrix tests.** Cover no binding, no matches, Permission denial, snapshot/history or revision error, illegal state/trust binding, Audit failure, Store/Retriever exception, and malformed `MemoryContext`. Assert Agent dispatch continues, fallback uses `memory_context=None`, queried-empty remains a real empty context, and trace contains only stage/status/target/domains/count.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/supervisor/test_memory_fallback.py -q
  ```

  Expected: current Supervisor either lacks Memory stages or treats enrichment failure as a workflow failure.
- [ ] **Step 3: Implement exact fallback behavior.** Catch sanitized Retrieval errors and unexpected injected Retriever faults at the optional enrichment boundary, discard every partial value, append `memory_fallback` with status `error` and count `0`, build planning context with `memory_context=None`, and continue Knowledge/planning/dispatch. On successful empty retrieval, append `memory_retrieved` with count `0` and preserve the empty context.
- [ ] **Step 4: Run GREEN.** Run fallback, integration, Agent, gateway, and dispatcher tests.
- [ ] **Step 5: Review.** Search trace and Agent metadata construction to prove no Permission reason, Audit event, exception type/text, path, payload count from failed reads, or record content is leaked.

**Completion condition:** Every Failure Matrix row continues the existing Agent workflow without unauthorized content disclosure.

### Task 11: Security Boundary

**Files:**
- Create: `tests/security/test_memory_intelligence_boundary.py`
- Modify: `tests/security/test_engineering_memory_boundary.py`

**Interfaces:**
- Consumes: fixed v0.40 package file set, Python AST, public exports, and v0.39 public contracts.
- Produces: static enforcement of read-only imports/calls/tokens and compatibility assertions.

- [ ] **Step 1: Write RED security tests.** Assert fixed file membership; no Store adapter/Aggregate/service/internal-container imports; only verified snapshot/history request construction; no mutation request tokens; no Agent/Model/LLM/RAG/Tool/Workspace/Git/Shell/subprocess/hardware calls in Retrieval; no filesystem/network/database/environment/time/UUID/random/cache/background/async/mutable module state; narrow factory/facade exports; unchanged Store eight methods, MemoryPort one method, Permission fields, Audit fields, and Verification signatures.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/security/test_memory_intelligence_boundary.py tests/security/test_engineering_memory_boundary.py -q
  ```

  Expected: the new boundary file or approved module set is absent.
- [ ] **Step 3: Make only boundary-compliance adjustments.** Remove prohibited imports/calls/exports, keep helpers private, and move Supervisor-only fusion behavior outside the Retrieval package. Do not weaken an assertion to accommodate a violation.
- [ ] **Step 4: Run GREEN.** Run both security files and existing Verification, Workspace, Tool, and Supervisor security regressions.
- [ ] **Step 5: Review.** Inspect the complete AST allowlist and token list against design sections 3 and 11–13.

**Completion condition:** Static gates prove the Retrieval package is deterministic, read-only, and unable to bypass v0.39 trust boundaries.

### Task 12: Testing Implementation

**Files:**
- Review: all new `tests/engineering_memory/test_*.py` listed above
- Review: all new `tests/supervisor/test_memory_*.py` listed above
- Review: `tests/services/test_analysis.py`
- Review: `tests/security/test_memory_intelligence_boundary.py`

**Interfaces:**
- Consumes: all public and internal behavior produced by Tasks 1–11.
- Produces: complete behavior coverage with deterministic fakes and no external services.

- [ ] **Step 1: Run the complete new-test RED/GREEN audit.** Confirm every design test bullet maps to a named test and no test passes without exercising its intended production branch.
- [ ] **Step 2: Run focused suites.**

  ```powershell
  python -m pytest tests/engineering_memory/test_retrieval_contracts.py tests/engineering_memory/test_read_projection.py tests/engineering_memory/test_retrieval.py tests/engineering_memory/test_domain_mapping.py tests/engineering_memory/test_ranking.py tests/engineering_memory/test_deterministic_ranking.py tests/engineering_memory/test_memory_context.py -q
  python -m pytest tests/supervisor/test_memory_fusion.py tests/supervisor/test_memory_integration.py tests/supervisor/test_memory_fallback.py tests/supervisor/test_memory_dispatch.py tests/services/test_analysis.py -q
  ```

  Expected: all focused tests pass with no warning-based exception.
- [ ] **Step 3: Close coverage gaps with explicit cases.** Use fake `EngineeringMemoryPort` instances that record immutable request copies; use fixed UTC timestamps and deterministic records; use barriers/events rather than sleep for revision-drift interleavings; assert no real database, network, filesystem, model, or hardware dependency is used.
- [ ] **Step 4: Run related regressions.** Run all `tests/engineering_memory`, `tests/supervisor`, `tests/agents`, `tests/services/test_analysis.py`, and `tests/integration/test_supervisor_integration.py`.
- [ ] **Step 5: Review.** Inspect test diffs for over-broad mocks, private-container access, ordering assumptions not specified by design, and accidental changes to historical tests.

**Completion condition:** Every item in design section 15 has a named deterministic test and all related regressions pass offline.

### Task 13: Release Contract Update

**Files:**
- Modify in the future implementation: `pyproject.toml`, `src/embedded_copilot/__init__.py`, `src/embedded_copilot/core/config.py`, `src/embedded_copilot/schemas/api.py`
- Modify in the future implementation: `README.md`, `docs/architecture.md`, `docs/PROJECT_CONTEXT.md`
- Create in the future implementation: `docs/release/v0.40.0.md`, `tests/release/test_v040_release.py`
- Modify in the future implementation: `tests/release/test_contract_compatibility.py`, `tests/release/test_release_metadata.py`

**Interfaces:**
- Consumes: completed and verified v0.40 behavior from Tasks 1–12.
- Produces: synchronized `0.40.0` package/runtime/health metadata and an accurate read-side release contract.

- [ ] **Step 1: Write RED release assertions.** Require `0.40.0` across package, project, Settings, and HealthResponse; require the v0.40 release document and architecture/context descriptions; preserve historical release-document assertions while removing only stale “current version remains 0.39.0” assertions.
- [ ] **Step 2: Run RED.**

  ```powershell
  python -m pytest tests/release/test_v040_release.py tests/release/test_contract_compatibility.py tests/release/test_release_metadata.py -q
  ```

  Expected: version and missing-document assertions fail against `0.39.0`.
- [ ] **Step 3: Apply minimal future release metadata changes.** Synchronize exact literals to `0.40.0`; document deterministic verified-only read-side retrieval, Memory/Knowledge separation, fallback, unchanged v0.39 contracts, and all non-goals. Describe the release tag strategy as annotated `v0.40.0`, created only after the separately approved implementation commit passes every gate.
- [ ] **Step 4: Run GREEN.** Run v0.40 plus all historical release and compatibility tests.
- [ ] **Step 5: Review.** Ensure documents do not claim persistent storage, autonomous learning, automatic Memory writes, automatic repair, hardware verification, Browser integration, or execution closure.

**Completion condition:** Future release metadata is synchronized and accurately describes only tested v0.40 behavior. The present documentation task does not perform these changes.

### Task 14: Full Validation and Release Gate

**Files:**
- Verify: complete future implementation tree
- Do not rewrite: unrelated historical dirty or formatting debt

**Interfaces:**
- Consumes: Tasks 1–13 and the repository quality policy.
- Produces: recorded evidence that the future implementation is eligible for separate release approval.

- [ ] **Step 1: Run focused and security gates.** Run all new Retrieval, ranking, context, Supervisor integration, fallback, service binding, and security files explicitly.
- [ ] **Step 2: Run regressions.** Run Engineering Memory, Supervisor, Agents, Analysis Service, Verification Agent, Workspace Runtime, Tool Runtime, release compatibility, and historical release suites.
- [ ] **Step 3: Run the complete offline suite.**

  ```powershell
  python -m pytest -q
  ```

  Expected: all tests pass; no failure is waived.
- [ ] **Step 4: Run quality gates.** Build the Python manifest from ACMR files relative to the approved implementation base, then run Ruff and Black only on that manifest. Run `python -m compileall -q src tests`, `python -m pip check`, and `git diff --check`. Do not use unsafe fixes or format unrelated historical files.
- [ ] **Step 5: Review the complete diff.** Confirm every changed production/test/release file is listed in this plan, every change maps to a design chapter, v0.39 public contracts remain unchanged, and excluded systems are absent.

**Completion condition:** All focused, regression, full-suite, quality, dependency, compile, and diff checks pass from the same future implementation tree. Failure blocks any feature commit or tag.

### Task 15: Precise Staging and Commit

**Files:**
- Add only: `docs/superpowers/plans/2026-07-30-memory-aware-engineering-intelligence-implementation-plan.md`

**Interfaces:**
- Consumes: this reviewed Implementation Plan document and design commit `ae4bbd0671fe62ee97b235b916b4752561ee6ef5`.
- Produces: one documentation commit named `docs: add v0.40 memory intelligence implementation plan`.

- [ ] **Step 1: Validate this plan document.** Strictly decode UTF-8, reject BOM, verify exactly 15 Task headings, verify the 16-row design coverage matrix, scan the attachment-specified forbidden terms, and confirm the document does not claim completed v0.40 implementation.
- [ ] **Step 2: Review the unstaged diff.** Run `git diff --check` and inspect the complete target-file diff. The worktree must contain no other modification.
- [ ] **Step 3: Stage only the target document.**

  ```powershell
  git add -- docs/superpowers/plans/2026-07-30-memory-aware-engineering-intelligence-implementation-plan.md
  git diff --cached --name-only
  git diff --cached
  git diff --cached --check
  git write-tree
  ```

  The cached name list must contain exactly the target plan path.
- [ ] **Step 4: Create the documentation commit.** Run `git commit -m "docs: add v0.40 memory intelligence implementation plan"` only after the staged tree passes review.
- [ ] **Step 5: Verify isolation.** Confirm commit parent equals `ae4bbd0671fe62ee97b235b916b4752561ee6ef5`, the commit adds only the target plan, the plan worktree is clean, and the original main HEAD/index/dirty list is unchanged. Do not create a tag and do not push.

**Completion condition:** The isolated branch contains one documentation commit over the design commit, with no production, test, version, release, README, or main-worktree mutation.

## Design Specification Coverage Matrix

| Design chapter | Implementation coverage |
|---|---|
| 1. Summary | Global Constraints; Tasks 3, 8, 9 |
| 2. Goals | Tasks 2–10 |
| 3. Non-goals | Global Constraints; Task 11 |
| 4. Current v0.39 Architecture | Locked Public Contracts; Tasks 2, 3, 11 |
| 5. v0.40 Architecture | File Responsibility Map; Tasks 3, 8, 9 |
| 6. Memory Retrieval Model | Tasks 1–3 |
| 7. Ranking Model | Tasks 4–6 |
| 8. Memory Context Contract | Tasks 1 and 7 |
| 9. Supervisor Integration | Tasks 8–10 |
| 10. Knowledge Gateway Fusion | Task 8 |
| 11. Security Boundary | Task 11 |
| 12. Permission Boundary | Tasks 3, 10, 11 |
| 13. Audit Boundary | Tasks 3, 10, 11 |
| 14. Failure Handling | Task 10 |
| 15. Testing Strategy | Tasks 1–12 and 14 |
| 16. Release Strategy | Tasks 13–15 |

## Plan Self-check

- [ ] The document strictly decodes as UTF-8 and has no UTF-8 BOM.
- [ ] Exactly 15 headings match `### Task <number>: <title>` and the numbers are consecutive.
- [ ] Every Task has Files, Interfaces, RED evidence, expected failure, minimum behavior, GREEN command, diff review, and completion condition; Tasks 14–15 express equivalent gate steps for validation and documentation delivery.
- [ ] All 16 design chapters map to at least one Task.
- [ ] All public type names, fields, signatures, score factors, child request semantics, and fingerprints are consistent across Tasks.
- [ ] The ranking formula and full tie-break order appear exactly once as locked behavior and are used consistently.
- [ ] Task 2 creates a new read-side projection and does not extend v0.39 Snapshot, Record, or Verification binding contracts.
- [ ] Permission and Audit remain behind `EngineeringMemoryPort.execute()` and receive no ranking, usage, payload, Knowledge, or Agent data.
- [ ] VERIFIED-only filtering, revision-bound history, fail-closed correlation, no partial result, and all six fallback situations are covered.
- [ ] The plan contains no second Supervisor, Store bypass, Memory mutation, implicit usage write, or forbidden external capability.
- [ ] The attachment-specified forbidden-pattern and vague-instruction scan returns no match.
- [ ] The document states that it is a plan and makes no completed-implementation claim.
- [ ] The documentation commit stages only this file, has the design commit as parent, creates no tag, and performs no push.

## Implementation Handoff

Future implementation requires separate explicit approval. Execute Tasks 1–14 in an isolated worktree with TDD and review checkpoints; Task 15 records only the present plan-document delivery chosen for this scope. A feature commit and annotated `v0.40.0` tag are outside this documentation task and require their own approved release instruction.
