# Embedded Copilot v0.47.0

## Hardware Intelligence Layer

新增：

- framework-independent、observation-only Hardware Intelligence Runtime
- immutable hardware intelligence contracts and deterministic fingerprints
- caller-owned Digital Twin Boundary with no built-in transport
- reference-only HIL Projection Boundary
- structured, finite Hardware Observation model
- approval-bound Validation Projection
- safe projection from verified Execution Integration snapshots
- framework, device, transport, persistence, and mutation Security Boundary

本版本不提供 physical hardware control、USB、Serial、Flash、Debug、real HIL
execution 或 physical hardware validation。`VALIDATED` 仅表示注入的结构、模拟、
阈值与 contract validation 已通过，不表示真实设备或电气设计已经验证。

# Embedded Copilot v0.46.0

## Execution Integration Layer

新增：

- framework-independent controlled `Execution Runtime`
- immutable, fingerprinted `Execution Plan` and terminal snapshot contracts
- one-shot exact `Executor Registry Boundary` with no fallback or discovery
- typed `Human Approval Binding` to the existing Human Loop review snapshot
- deterministic `Controlled Execution Lifecycle` and safe progress events
- result-bound `Verification Projection`
- sanitized timeout, cancellation, verification, and `Failure Snapshot` handling
- process-local sequential and concurrent `Replay Protection`
- framework, transport, filesystem, hardware, and provider `Security Boundary`

本版本只提供受控执行抽象。生产 package 不提供真实 executor，不执行 real Build、
real Flash、real Hardware Debug、Shell、Git、network、filesystem mutation 或
hardware control；cross-process replay protection 仍是非目标。

# Embedded Copilot v0.45.0

## Human Loop Layer

新增：

- framework-independent、human-controlled Human Loop Runtime
- metadata-only Proposal Projection 与 deterministic fingerprint binding
- explicit Human Review Lifecycle：APPROVED、CHANGES_REQUESTED、REJECTED
- structured Feedback Projection 与 safe reference boundary
- verified Knowledge/Memory reference-bound Revision Context
- reviewable Revision Proposal Boundary
- content-safe Progress Event Isolation 与 Security Boundary

本版本不提供 automatic approval、artifact mutation、Agent execution、Tool execution、Build、
Flash、Hardware Debug、Memory writes 或 Knowledge mutation。Revision Proposal 必须重新进入
Human Review。

# Embedded Copilot v0.44.0

## Engineering Generation Layer

新增：

- framework-independent、approval-controlled Engineering Generation Runtime
- exact Generator capability binding 与无 fallback Registry boundary
- immutable、fingerprinted Artifact Proposal model
- Hardware/Firmware/PCB/BOM typed generation boundary
- independent Verification lifecycle 与 Human Approval workflow
- content-safe progress events 与 Security Isolation boundary

本版本只产生可审查的工程提案和 Approved Artifact Reference，不生成真实 PCB 文件、不修改工程
文件，也不执行 Build、Flash、Hardware Debug 或 Tool Runtime capability。

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
