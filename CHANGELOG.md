# Embedded Copilot v0.43.0

## Agent Execution Layer

新增：

- framework-independent、controlled-execution `AgentExecutionRuntime`
- explicit Agent Registry binding 与 caller-owned execution capability
- deterministic execution lifecycle 和 content-safe progress events
- typed result preservation、Safe Result Projection 与 Verification Boundary

## Failure Handling and Recovery

新增：

- registry、agent、timeout 和 verification failure 的 fail-safe Execution Snapshot
- 两阶段人工恢复，最多一次 approved resume
- approval fingerprint binding、旧 snapshot replay rejection 和 denial cancellation

## Security Boundary

- 不推断 Agent type，不动态发现或导入 Agent implementation
- 不调用 Tool Runtime、Workspace write、Build、Flash 或 Hardware Debug
- 不保存 prompt、reasoning、raw output、live execution port 或内部异常

## Testing

Release candidate validation：

- pytest: 2256 passed, 6 skipped
- Ruff: passed
- scoped Black check: passed
- compileall: passed
- pip check: passed
- git diff check: passed

# Embedded Copilot v0.42.0

## Agent Workflow Layer

新增：

- framework-independent、planning-only `WorkflowRuntime`
- injected Requirement Agent、Workflow Context 和 Engineering Planning ports
- typed output preservation、deep-copy revalidation 与 deterministic fingerprints
- strict `WorkflowRiskProjection` 和 verified source binding

## Task DAG and Scheduling

新增：

- immutable Frozen Task DAG
- missing dependency、duplicate edge、self-edge 和 cycle validation
- deterministic Kahn scheduling batches
- Risk 与 task priority、scheduling order、DAG mutation 和 Agent selection 隔离

## Human Approval and Progress

新增：

- whole-workflow approval binding
- approval 前停止于 `WAITING_APPROVAL`
- caller-timestamped、content-safe Progress Events
- progress sink fail-closed boundary

## Security Boundary

- 不执行 task、Tool、build、firmware/PCB generation、Flash 或 hardware control
- 不导入 Supervisor、Knowledge 或 Engineering Memory 内部实现
- 不读取 filesystem、network、database、environment 或 system clock
- 不缓存、不持久化，不生成 ID，不启动 background task

## Testing

Release Preparation validation 将在 release commit/tag 前完成并记录。

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
