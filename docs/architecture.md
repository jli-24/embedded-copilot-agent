# Embedded Copilot Agent Architecture

## v0.41 Knowledge Intelligence Layer

```text
External Knowledge Source
  -> Knowledge Candidate Evidence
  -> Knowledge Verification
  -> Verified Knowledge Evidence + KnowledgeProvenance
  -> Knowledge Graph Projection
  -> Supervisor Planning Context
  -> Engineering Memory Bridge [candidate projection only]
```

该图表示 evidence 的投影顺序，不表示 Graph 或 Memory Bridge 获得控制权。Supervisor 始终是
任务选择和路由的唯一所有者；Memory Bridge 是独立的只读 candidate projection。

`KnowledgeIntelligenceRuntime` 是独立、framework-independent、read-only 的增强层，facade
只公开 `knowledge_port()`。所有输入输出使用 frozen、`extra="forbid"`、tuple-only DTO；Runtime
不读取系统时钟、不生成 ID，也不缓存或持久化 source、evidence、graph 或 memory candidate。

Web Research 只调用构造期注入的 `WebResearchSourcePort`，每个请求最多一次，不包含 browser、
HTTP client、crawler、retry loop 或后台任务。Datasheet 路径只消费调用方显式提供的
`DatasheetRequest`，复用既有 `DatasheetIntelligencePort`，不下载 PDF、不猜测路径、不读取 bytes。

Verification 使用不可变 `SourceTrustCatalog`。无冲突的权威来源允许单源 VERIFIED；Community/Web
必须由至少两个独立 publisher 提供相同 canonical fact。同一 publisher 的重复结果不能形成多源；
矛盾事实进入 REVIEW_REQUIRED，未知来源进入 REJECTED。Provider 自报 confidence 不参与信任判断。
每条 VERIFIED evidence 携带 `KnowledgeProvenance`，记录 source type、publisher、reference、
verification method、调用方提供的 UTC 时间和固定 verified confidence。

Knowledge Graph 是 Verified Evidence 的纯函数投影。Snapshot 使用 canonical JSON、稳定排序与
SHA-256 fingerprint；query 只返回 evidence projection。它不生成任务、不选择 Agent、不构造
`SupervisorPlan`、不调用 Tool，也不触发执行。首版只投影显式 `conflicts` relation，不推断未声明的
GPIO、电气或时序冲突；不引入 Neo4j、database、JSON persistence 或 mutable global graph。

Memory Bridge 只把 VERIFIED Failure Rule 投影为可审查的 `KnownIssueMemory` candidate 和既有
`CreateCandidateRequest` binding。它不持有或调用 `EngineeringMemoryPort`，不创建 VERIFIED record，
不生成 `ApplyVerificationRequest`，也不自动修改永久规则。后续写入仍经过既有 Permission、Audit、
Verification/Human Approval lifecycle。Workspace Runtime 继续保持唯一文件写边界。

Supervisor 对 Knowledge Intelligence 的依赖是可选的。未注入时保持 v0.40 Knowledge Gateway
行为；注入后每次 run 最多调用一次 `retrieve()`，并且只有 VERIFIED evidence 可以进入 Planning。
失败时使用 memory-only 或 empty planning context 安全降级。Agent handoff 不包含 graph snapshot、
raw evidence、source content、verification body 或 Memory proposal；`knowledge_trace` 仅记录固定的
sequence、stage、status、count 和 source type。

## v0.39 Engineering Memory Layer

Engineering Memory 是独立、framework-independent 的同步领域层。唯一公共业务入口为
`EngineeringMemoryPort.execute()`；facade 只公开 `memory_port()`。调用方提供的 strict
frozen command 先经过重新验证和 canonical SHA-256，再依次通过无内容 audit、最小披露
permission、原子 Store operation 与终态 audit。

首版 `InMemoryEngineeringMemoryStore` 以每实例私有 `RLock` 保护 Aggregate。receipt
检查、revision 检查、状态转换、双记录替代、projection 更新和 receipt 写入均在同一个锁
保护的 Store 临界区内完成。History cursor 固定绑定 aggregate revision，Verification
History identity 为 append-only。

`CANDIDATE` 与 `VERIFIED` 明确隔离。技术事实必须消费调用方提供的 Verification
request/result；仅 Engineering Decision 与 Known Issue 允许受限 Human Approval。
Memory 不调用 Verification Agent、Agent、LLM、RAG 或 Tool，不访问 filesystem、network、
database 或硬件，不提供 hard delete。Workspace Runtime 保持唯一文件写边界。

## v0.38 Verification Agent Layer

```text
Engineering Result
  -> strict VerificationRequest
  -> injected deterministic Checker tuple
  -> atomic checker batch
  -> VerificationResult
  -> Verified Decision candidate
```

`embedded_copilot.verification_agent` 是独立、framework-independent 的确定性验证基础层。
公共 facade 只暴露同步 `VerificationPort`；可信 composition 注入 Checker tuple 与无内容
audit sink。Firmware、Hardware 与 Tool Result subject 只复用既有 Runtime 公开 DTO，Checker
不持有 Runtime Port，也不调用 Agent、Model、Tool、Shell、文件系统、网络或硬件。

多 Checker 构成原子验证批次：任一 Checker 缺失、异常或返回畸形结果时立即停止，不执行
后续 Checker，不返回部分 `VerificationResult`，并记录 `VERIFICATION_FAILED`。正常结果按
`FAIL > REVIEW_REQUIRED > PASS` 聚合，Finding 始终为 `candidate_semantics="unverified"`。
`FAIL` 表示当前提案未通过验证规则，不表示已确认真实设备故障；候选输入是否同时启用仍需
工程师确认。

该层不执行 Tool、不修改文件、不自动修复、不调用 Agent 或 LLM、不控制硬件。Workspace
Runtime 继续作为唯一文件写入口。

## v0.37 Tool Execution Layer

```text
ToolExecutionContext
  -> required TOOL_REQUESTED audit
  -> caller-owned ToolPermissionPort
  -> immutable adapter registry
  -> EngineeringToolPort
  -> normalized ToolResult
  -> required terminal audit
```

`embedded_copilot.tool_runtime` 是独立、framework-independent 的受控能力执行基础层。
公共 facade 只暴露同步 `ToolExecutionPort`；可信 composition 通过不可变 tuple
注入 `EngineeringToolPort`、权限端口和 audit sink。授权结果与 request、tool、
caller 以及完整参数 fingerprint 精确绑定，不存在 fallback 或全局权限状态。

`adapters/` 只负责把既有公共 Runtime Port 或显式 Mock scenario 适配为受控能力。
`compile_firmware` 与 `run_firmware_test` 在 v0.37 中只提供强制标记为 `MOCK`
的确定性场景；`read_serial_log` 只调用一次公共 `DebugPort` UART snapshot，并丢弃
target identity、register、stack 与其他非串口内容。

Runtime 不接入 Agent、Supervisor、API 或 UI，不读取或修改文件，不执行 Shell、
Git、真实 build/test、Flash、reset 或硬件控制。Workspace Runtime 继续作为唯一
文件写入口。

## v0.36 Telemetry Intelligence Layer

```text
caller-owned TelemetrySourcePort tuple
  -> TelemetryRuntime
  -> TelemetrySample / bounded TelemetrySeriesSnapshot
  -> deterministic statistics / endpoint trend / anomaly candidate
  -> content-free TelemetryAuditEvent
```

`embedded_copilot.telemetry_runtime` 是独立、deterministic、observation-only 的数值
telemetry 基础层。Runtime 只通过 `TelemetryPort` 暴露同步 sample、series 和 analysis
操作；精确按 `DEBUG_RUNTIME` 或 `MOCK` source type 路由且不 fallback。source 的连接、
生命周期和数据采集方式完全由 caller 管理。

单点与序列都使用 canonical JSON 和 SHA-256 指纹并在构造时复核。序列只在当前请求内进行
2 到 256 次 bounded synchronous pull，不 sleep、不轮询、不缓存或跨请求积累。分析只计算
minimum、maximum、average、endpoint delta 与 endpoint direction trend；阈值越界只生成
`unverified` candidate，不产生 root cause、confirmed fault、control action 或自动修复。

`DebugTelemetryContext` 只从 Debug Runtime 公共 `FrozenDebugSnapshot` 投影 telemetry
metrics，不持有 `DebugPort`，也不传播 identity、UART、register 或 stack 内容。该 Runtime
不实现 Agent、LLM、RAG、PID、自动调参、硬件控制、Flash、reset、真实 transport、API、
UI、网络、文件系统、后台任务、缓存或持久化。

## v0.35 Embedded Debug Runtime

```text
caller-owned DebugSourcePort tuple
  -> DebugRuntime
  -> source-specific read-only adapter
  -> normalized TargetIdentity / Debug Snapshot / Telemetry
  -> content-free DebugAuditEvent
```

`embedded_copilot.debug_runtime` is a framework-independent, observation-only
hardware debug foundation. Its factory accepts a non-empty immutable tuple of
caller-owned UART, J-Link, ST-Link, or GDB source ports. Routing is exact by
source type, never falls back, and does not own connections, device handles,
processes, transports, credentials, or provider lifecycle.

Each operation performs one synchronous, request-scoped observation and emits a
corresponding content-free audit event using the caller-provided UTC timestamp.
Snapshots contain only bounded normalized UART records, register summaries,
stack-frame summaries, and finite telemetry metrics. They do not contain source
code, paths, locals, arguments, memory buffers, firmware images, credentials, or
device secrets.

The Runtime does not implement a hardware transport, Agent, model invocation,
automatic debugging, API, UI, network, filesystem access, Shell, Git, build,
flash, reset, register or memory mutation. Workspace Runtime remains the only
file write boundary.

## v0.34 VS Code MCP Integration Layer

```text
VS Code tool request
  -> transport-neutral MCP adapter contract
  -> VSCodePort
  -> CodingIntelligencePort / WorkspacePort
```

`embedded_copilot.vscode_runtime` performs only deterministic argument
validation, DTO conversion, capability gating, and invocation of existing public
Runtime ports. Callers provide source text, compiler logs, diffs, proposal IDs,
and approval timestamps explicitly; the integration layer does not read files,
scan directories, execute commands, persist content, or generate authority.

The default adapter exposes five non-mutating tools. Applying a change requires
construction-time opt-in and a caller-provided `ApprovalContext`, while Workspace
Runtime remains the only write boundary and revalidates the complete proposal,
snapshot, target, and approval binding. `create_change_proposal` always calls
`WorkspacePort.validate_change()` so an unvalidated proposal cannot enter the
approval flow.

v0.34 is an MCP adapter contract foundation. It has no MCP SDK dependency and
does not start an MCP server or implement stdio, HTTP, WebSocket, network, IDE,
Shell, Git, build, flash, or hardware-control transport.

## v0.33 Workspace Operation Layer

```text
trusted workspace root + explicit relative paths
  -> frozen Workspace Snapshot
  -> ChangeProposal unified diff
  -> current-content validation
  -> external human approval
  -> private FileWritePort
  -> content-free audit event
```

`embedded_copilot.workspace_runtime` is an independent, approval-gated mutation
capability. It is not an Agent, workflow, IDE integration, Shell, Git, or build
runner. The factory owns one trusted root; requests cannot scan directories or
address files outside that root. Snapshots contain only normalized paths, hashes,
sizes, and language classifications.

Only an existing UTF-8 text file represented by a verified snapshot may receive a
strict unified diff. Validation binds the target file and its parent directory
chain to descriptor-derived identities, verifies the snapshot hash, and
precomputes every output before approval. A process-local canonical proposal
fingerprint prevents an approval from being reused with altered diff, reason, or
creator fields. `apply_change()` repeats validation, checks the externally
supplied approval binding, and then uses same-directory temporary files plus
recovery backups for controlled replacement and reverse rollback. Audit output
contains identifiers, relative paths, approval identity, and supplied UTC time,
never file content, hashes, diff text, tokens, or secrets.

The cross-platform implementation binds descriptor-derived identities and hashes
but does not add platform-specific native-handle traversal. `APPLIED` is a
process-level result, not a crash-durability guarantee, and callers serialize
operations for each runtime instance.

## v0.32 Coding Intelligence Layer

```text
caller-provided bounded code DTOs
  -> CodingIntelligencePort
  -> frozen, fingerprinted Code Context Snapshot
  -> deterministic Project / Build / Diff / Dependency analyzers
  -> unverified hardware/software candidates
```

`embedded_copilot.coding_runtime` is an independent read-only capability, not an
Agent or workflow. `CodingRuntime` exposes only `coding_port()`; callers provide
bounded source text, compiler diagnostics, unified diffs, and hardware candidates
through frozen DTOs. The generated snapshot contains normalized relative paths,
content hashes, line counts, symbols, dependencies, and explicit hardware-access
candidates, never source text.

The runtime does not read a workspace, run Git or a compiler, modify code, call a
model, control an IDE, or access a device. C/C++ parsing is Tree-sitter based and
Python parsing uses `ast`; project marker analysis is deterministic. Any
hardware/software relationship is a datasheet-bound, unverified candidate that
requires engineer review rather than an engineering fact or confirmed conflict.

## v0.19 Productization Flow

```text
Streamlit metadata builder / Demo manifest
  -> JSON metadata only
  -> FastAPI /api/v1/analyze
  -> AnalysisService
  -> attach_input_context()
  -> SupervisorAgent
  -> EngineeringReport
  -> in-memory ExecutionRegistry
  -> status/report API
  -> EngineeringReport viewer
```

API Layer 不导入领域 Agent 实现。Streamlit 不导入 Supervisor、Agent、Parser、
Knowledge Gateway 或旧 `multimodal/`。只有 `AnalysisService` 构造 `AgentTask`、通过
Supervisor adapter 注入 `UnifiedInputContext` 并调用 Supervisor。Registry 只保存状态、
安全错误或 `EngineeringReport`，单 worker、容量 100、默认超时 120 秒，进程重启后清空。

附件内容不会上传、读取、持久化、解析、缓存或索引。Demo fixture 只由 manifest 描述；
UI 和分析链不读取 fixture 正文。报告 viewer 只显示已有 evidence、recommendation 与
trace，不调用 LLM，也不序列化 PCB/Datasheet model。

## v0.18 Embedded Copilot Integration Flow

```text
User request + UnifiedInputContext [metadata-only]
  -> SupervisorAgent [only orchestration owner]
  -> SupervisorRequirementAnalyzer
  -> IntegrationPlanner [Agent selection only]
  -> KnowledgeQueryBuilder -> KnowledgeGateway [optional, Supervisor-owned]
  -> SupervisorPlanner
  -> AgentExecutor -> existing AgentDispatcher
       -> FirmwareAgent -> HardwareAgent -> PCBAgent -> DebugAgent
  -> validate FirmwareProject / HardwarePlan / PCBReviewReport / DebugReport
  -> immutable content-safe evidence snapshots
  -> ResultAggregator [aggregation-only]
  -> EngineeringReport [JSON / Markdown]
```

Integration Layer 位于 `embedded_copilot.integration`，只负责编排和结构化投影，不实现 Firmware、
Hardware、PCB 或 Debug 领域知识。`IntegrationPlanner` 的唯一输出是 canonical Agent tuple；它使用
request、`UnifiedInputContext.text`、attachment basename/type/format 和可选 validated structure
model presence 做离线 deterministic selection，不读取附件内容，也不产生工程结论。

`AgentExecutor` 只调用 Supervisor 已拥有的 `AgentDispatcher`。固定依赖顺序为
`FirmwareAgent -> HardwareAgent -> PCBAgent -> DebugAgent`，继续保留 FirmwareProject 和
HardwarePlan typed handoff。Executor 不修改 Agent output；原 output 继续进入 legacy Supervisor result，
Integration 旁路验证成功 output 是否符合既有领域模型并投影为不含正文、metadata 或 mutable collection
的 evidence snapshot。失败保持为该 Agent 的结构化 error 并继续后续执行。领域 Agent 不持有或调用 Gateway。

`ResultAggregator` 只把 immutable evidence snapshot 聚合为 report sections。所有 section、finding、
recommendation 与 trace event 都携带 `source_agent` 和 `source_id`。顶层 recommendation 仅复制
PCB issue 和 Debug report 已存在的 recommendation，Aggregator 不生成新 recommendation。Firmware
只报告 relative file path，不报告 file content；PCB/Datasheet structure model、Knowledge content、
PDF 正文、PCB 原始内容、日志全文、绝对路径和 secret 均不会进入 EngineeringReport。

原 `SupervisorAgent.run(AgentTask) -> AgentResult`、`AgentResult.output` 中的 `SupervisorResult`、
Agent public API、Knowledge Gateway/Provider Contract、Benchmark public models/metrics 和四个领域
输出 schema 均保持不变。`engineering_report` 是成功完成 dispatch 后新增的 metadata 字段。
Integration 不调用 LLM，不创建 Parser、Provider、cache、index、temp file 或网络依赖；v0.17
Datasheet Parser/Adapter、v0.16 PCB Parser/Adapter 和旧 `multimodal/` 均不修改。

## v0.17 Datasheet Intelligence Foundation Flow

```text
trusted root + explicit attachment-id mapping
  -> InputLoader [metadata-only]
  -> MarkdownDatasheetParser / PDFDatasheetParser [single-target, bounded]
  -> UnifiedDatasheetModel [only Datasheet structure exchange model]
  -> Datasheet Adapter [canonical domain evidence]
  -> existing in-memory domain retriever
  -> unchanged HardwareAgent / PCBAgent / FirmwareAgent
```

Datasheet Parser 与领域 Agent 分层。Parser 只读取 `UserAttachment` 显式映射的单个目标，
复核 root containment、basename、document type、MIME、size、regular-file 与 symlink，
不扫描目录。Markdown 只解析固定标签和标准 section table；PDF 只解析有文本层且抽取后仍为
明确标签的行，并同时限制文件大小、页数和文本长度。复杂表格不做几何重建，无法可靠识别时
忽略或安全失败。Parser 不依赖 `multimodal/`、旧 RAG loader、Agent、Supervisor、Knowledge
Gateway、LLM 或网络，也不保存正文、AST、缓存、索引或中间文件。

`UnifiedDatasheetModel` 使用 frozen nested models、tuple collections 与 deep-copied、
scalar-only immutable metadata。同一文档产生相同的 component、pin、interface、electrical
evidence 与序列化结果。Adapter 只生成 bounded canonical JSON evidence 和稳定 provenance，
不产生设计建议或自动选型 metadata。现有领域 Agent 仅通过已有 retriever constructor 接收
document；没有 Datasheet 时继续执行 v0.16 legacy path。

## v0.16 PCB Intelligence Foundation Flow

```text
trusted root + explicit attachment-id mapping
  -> PCBSourceResolver
  -> KiCadPCBParser [single-target, read-only, bounded]
  -> UnifiedPCBModel [immutable structure exchange model]
  -> PCB evidence rules [deterministic, evidence-only]
  -> PCB analysis adapter [private frozen envelope]
  -> unchanged PCBAgent.run(AgentTask)
  -> unchanged PCBReviewReport schema
```

Parser 与 Agent 分层。`pcb/parser` 只依赖 `UserAttachment`、PCB parser contracts 和
`UnifiedPCBModel`，不依赖 PCBAgent、Supervisor、Knowledge Gateway 或 Provider。Resolver
不扫描 root；它只把 attachment id 映射到一个相对目标。Parser 重新验证 root containment、
basename、EDA type、MIME、size、regular-file 和 symlink，随后以 read-only 模式读取该目标一次。
原始 bytes、text 和 S-expression AST 只存在于单次 `parse()` 调用栈，不写入对象状态、缓存、
索引、中间文件或日志。

`UnifiedPCBModel` 是跨 Parser、Rule 和 Agent Adapter 的唯一 PCB 结构模型。其 components、pins、
nets、nodes、layers、tracks、vias 和 zones 使用 frozen nested model 与 tuple，metadata 在
deep-copy 后限制为只读 scalar。Parser 对不完整或超出已支持 KiCad 子集的结构安全失败，不通过
目录搜索或宽松猜测扩大解析范围。

结构规则只输出 power-net、ground-net 和 floating-pin evidence，不生成 risk score 或 LLM
recommendation；同一模型输入产生完全一致的有序结果。Adapter 使用固定映射生成旧
`PCBRuleEvaluation`，并通过不可伪造的私有 envelope 注入现有 `AgentTask.metadata`。PCBAgent
不读取文件、不解析 KiCad，只消费 `UnifiedPCBModel`；legacy text 和 HardwarePlan 路径保持不变。
该 Foundation 不执行 DRC、电气验证、Vision、OCR、自动布线或 EDA 写回。

## v0.15 Multimodal Input Foundation Flow

```text
User text + trusted-root relative attachment paths
  |
  v
InputLoader  [metadata-only, content-blind]
  |
  v
UserAttachment tuple -> UnifiedInputContext
  |
  v
attach_input_context() -> private frozen envelope -> unchanged AgentTask
  |
  v
SupervisorRequirementAnalyzer -> SupervisorTask.input_context
  |
  v
existing text-based routing -> Planner -> domain Agents
```

Input Layer 与 Runtime Agent 职责分离。Loader 只能执行 root containment、symlink、regular-file、
size、extension 和 MIME 验证；它不读取内容，不创建缓存、文件副本、sidecar、vector store 或
索引。`UserAttachment` 只保存 basename、canonical MIME、size、type 和 `format/category`
provenance。`UnifiedInputContext` 使用 tuple attachments 和 deep-copied、scalar-only、只读
metadata，不保留 nested mutable state。

Supervisor adapter 是唯一注入边界。Analyzer 只接受 adapter 创建的私有 envelope，普通 metadata
payload 不能伪装成 context。Planner 和 Dispatcher 不传播 context，领域 Agent、KnowledgeGateway、
Provider Contract、Benchmark public models 与原 `AgentTask` schema 保持不变。v0.15 当时的路由仍由
text rules 决定；v0.18 的 Supervisor-owned IntegrationPlanner 才开始消费附件的安全元信息，仍不读取内容。

`embedded_copilot.multimodal` 的旧 PDF、image 和 text content processors 不在该数据流中，
不调用、不迁移、不修改。PCB 与 Datasheet 内容解析分别属于上面的独立 v0.16/v0.17 Parser 边界，
不进入 v0.18 Integration Layer。

## v0.14 GitHub Provider Flow

```text
SupervisorAgent.run()
  -> KnowledgeGateway.search()
  -> ProviderRegistry.search()
  -> GitHubKnowledgeProvider
  -> explicitly injected GitHubClient
  -> ordered KnowledgeResult candidates
  -> KnowledgeGateway ranking / deduplication / global top-k
  -> KnowledgeContext
  -> domain knowledge adapters
  -> domain Agents
```

GitHub 是 knowledge Provider，不是 Agent。Supervisor、Agent 和 Gateway 不导入 GitHub raw
models；raw repository、code、issue、release contracts 只由 client 与 Provider 使用。
Provider 不拥有 ranking、deduplication 或 top-k。内容通过确定性 whitespace normalization 与
2000 字符截断生成，provenance metadata 和 reference URL 使用固定 allowlist。

`FakeGitHubClient` 只接受显式 synthetic fixtures。未注入 client 时返回空 candidates，不使
Gateway 或 Supervisor 失败。v0.14 不包含 HTTP、真实 GitHub API、网页抓取、clone、源码下载、
Token 配置、缓存、数据库、LLM 或 LangGraph Runtime。

## v0.13 Knowledge Provider Flow

```text
SupervisorAgent.run()
  -> KnowledgeGateway.search()
  -> ProviderRegistry.search()
       -> LocalKnowledgeProvider
       -> explicitly injected offline fixture providers
  -> ordered candidates
  -> KnowledgeGateway ranking / deduplication / global top-k
  -> KnowledgeContext
  -> domain knowledge adapters
  -> domain Agents
```

`KnowledgeProvider` 是 runtime-checkable `Protocol`，不要求实现类继承。ProviderRegistry
拥有 Provider 注册、移除、调用、source filter、query mutation 检查、返回值重验证和稳定
candidate 合并；它不拥有 ranking、deduplication、source priority 或 top-k。统一检索策略
只属于 KnowledgeGateway，Supervisor 与领域 Agent 均不感知 Registry。

Local Provider 的 filesystem 模式只接受调用方显式注入的 root，构造时对 canonical
`firmware`、`hardware`、`pcb`、`debug` 目录建立一次性只读 snapshot；legacy retriever
模式继续兼容原 import path 与 `add_documents()`。两种模式互斥，均不读取 Settings 或隐式
仓库路径。v0.13 不包含真实 Web/GitHub Provider、HTTP、下载、LLM 或 LangGraph Runtime。

## v0.12 Foundation Supervisor Knowledge Flow

```text
User / AgentTask
  |
  v
SupervisorAgent.run()
  |
  +--> SupervisorRequirementAnalyzer
  +--> KnowledgeQueryBuilder
  +--> KnowledgeGateway.search()  [0..1 call per run]
  +--> KnowledgeContext
  +--> SupervisorPlanner
  +--> AgentDispatcher
         |
         +--> supervisor knowledge adapters
         +--> FirmwareAgent
         +--> HardwareAgent
         +--> PCBAgent
         `--> DebugAgent
  |
  v
SupervisorResultAggregator
```

Gateway invocation ownership belongs exclusively to `SupervisorAgent.run()`。
Planner、Dispatcher、adapter 和领域 Agent 均不得持有或调用 Gateway。Supervisor 在调用
Gateway 前重新验证并 deep copy query，在调用后比较稳定快照；Gateway 返回值按当前公开
契约重新验证，保持原顺序，不重新 rank 或 deduplicate。

`ExecutionContext` 是 Supervisor 内部的 frozen 传递对象，包含原始 task 的独立副本、
`KnowledgeContext`、受限 trace 和每次执行生成的 `execution_id`。它不会整体序列化到
`AgentTask.metadata`。Dispatcher 的内部 contextual path 通过 Supervisor 层 adapter 将
结果转换为领域模型，只注入最小知识输入、安全 provenance 和 centralized mode 标记。

依赖方向固定为：

```text
Supervisor -> KnowledgeGateway -> KnowledgeResult
           -> knowledge adapters -> domain models -> domain Agents
```

领域 Agent 不依赖 Supervisor context 模型。显式 Gateway 模式下，即使某领域过滤结果为空，
也不会回退本地 retriever；`knowledge_gateway=None` 时仍执行 v0.11 原路径。显式 Gateway
trace 仅包含 `stage`、`status`、`target`、`domains` 和 `count`。该集成不增加 Provider、
网络访问、LLM 或 LangGraph Runtime。

## Runtime Flow

```text
User
  |
  v
FastAPI
  |
  v
Supervisor Agent
  |
  +--> Knowledge Agent --> document_search_tool --> RAG / Chroma
  |
  +--> Firmware Agent  --> code_analysis_tool
  |
  +--> Debug Agent     --> debug_log_tool
  |
  v
Structured ChatResponse
```

每个请求最多选择一个 Specialist Agent。v0.1 Graph 没有循环：

```text
START -> supervisor -> specialist | clarification -> response -> END
```

## Boundaries

- `agents/` 只负责 routing、State update 和 Tool 调用。
- `tools/` 是外部能力边界，使用 Pydantic schema、timeout 和结构化错误。
- `rag/` 分离 loading、splitting、embedding、indexing 和 retrieval。
- `api/` 只处理 HTTP validation、dependency composition 和 error mapping。
- `services/` 提供配置、LLM adapter 和 application orchestration。
- `schemas/` 保存跨模块共享的 public contracts。

Runtime Agent 不直接访问 filesystem、shell、network、compiler 或 device。
知识文件和 Chroma 由 API lifespan 的 composition root 初始化，Agent 只能调用
注入的 Tool。

## State and Termination

`AgentState` 保存 trace ID、输入、intent、selected agents、messages、results、
sources、errors、final answer 和 terminal status。节点返回 partial update，不原地
修改 State。Unknown intent 进入 `NEEDS_CLARIFICATION`；Tool failure 进入
`FAILED`；正常 Specialist 进入 `COMPLETED`。

## Observability

每次闭环记录：

- `workflow_start`
- `agent_selected`
- `tool_called`
- `tool_completed`
- `error_occurred`，仅错误路径
- `workflow_completed`

事件传播同一个 trace ID，不记录 API Key、Token、私有文档正文或敏感本地路径。

## Limitations

离线 Hash Embedding 与 deterministic answer fallback 只用于 v0.1 可运行闭环。
真实模型、Datasheet、MCU/SDK 版本、硬件测量和编译证据缺失时，系统必须明确
说明限制，不能声称代码或诊断已经在硬件上验证。
