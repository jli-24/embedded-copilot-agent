# Embedded Copilot Agent v0.18 Architecture

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
