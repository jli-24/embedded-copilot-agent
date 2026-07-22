# Embedded Copilot Agent v0.1 Architecture

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
