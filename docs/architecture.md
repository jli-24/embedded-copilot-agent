# Embedded Copilot Agent v0.1 Architecture

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
