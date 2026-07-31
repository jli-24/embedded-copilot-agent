# Embedded Copilot v0.41.0

## Knowledge Intelligence Layer

新增：

- framework-independent `KnowledgeIntelligenceRuntime`
- transport-neutral `WebResearchSourcePort`
- existing Datasheet Runtime typed delegation
- deterministic source trust verification
- Verified Evidence 与 `KnowledgeProvenance`

## Knowledge Graph

新增：

- deterministic entity/relation projection
- canonical JSON + SHA-256 immutable snapshot
- evidence-only graph query
- explicit conflict relationship projection

Knowledge Graph 不生成任务、不选择 Agent、不构造 `SupervisorPlan`，也不触发执行。

## Memory Learning Bridge

新增：

- VERIFIED Failure Rule 到 `KnownIssueMemory` CANDIDATE 的只读投影
- existing `CreateCandidateRequest` binding

Memory Bridge 不调用 `EngineeringMemoryPort.execute()`，不创建 VERIFIED record，也不自动修改永久规则。

## Supervisor Integration

新增：

- optional `KnowledgeIntelligencePort` enrichment
- verified-only Planning projection
- content-safe `knowledge_trace`
- memory-only / empty-context failure fallback

## Security Boundary

- 不内置 browser、HTTP client、crawler 或 PDF download
- 不使用 Neo4j、database、filesystem persistence 或 mutable global graph
- 不实现自主搜索循环、后台任务或自动 Memory mutation
- Workspace Runtime 继续保持唯一文件写边界

## Testing

Release candidate validation：

- pytest: 2197 passed, 6 skipped
- Ruff: passed
- compileall: passed
- git diff check: passed

# Embedded Copilot v0.40.0

## Memory Intelligence Layer

新增：

- Engineering Memory Contract
- Verified Memory Read Projection
- Retrieval Pipeline
- Deterministic Ranking
- Ranked Context Builder
- Context Fingerprint

## Knowledge Gateway

新增：

- Knowledge Source Fusion
- Engineering Planning Context
- Memory + Knowledge Fusion

## Supervisor Runtime

新增：

- Memory-aware Supervisor
- Memory retrieval integration
- Failure fallback boundary
- Typed Input Envelope Preservation
- Secure metadata projection

## Engineering Runtime

新增：

- Hardware/Firmware runtime extension support
- Engineering report generation regression support

## Security Boundary

新增：

- Legacy Agent Result sanitization
- Metadata leakage prevention
- Typed context isolation

## Testing

Release validation:

- pytest: 2181 passed, 6 skipped
- ruff: passed
- compileall: passed
