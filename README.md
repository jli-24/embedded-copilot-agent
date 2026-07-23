# Embedded Copilot Agent

Embedded Copilot Agent v0.5.0 是面向嵌入式开发者的 Foundation Agent
System。它使用 LangGraph 将请求显式路由到 Knowledge、Firmware 或 Debug
Agent，并通过 typed Tool、RAG 与 FastAPI 返回结构化结果。

当前版本不是通用聊天机器人，也不是 EDA、自动烧录或硬件测试系统。

## Requirements

- Python 3.11
- pip

## Setup

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m pip install --no-deps -e .
```

复制 `.env.example` 为 `.env` 后可覆盖配置。默认 `offline` 模式不需要 API
Key、网络、硬件或串口。

## Development Environment

开发环境固定使用 Python 3.11。创建并激活虚拟环境后，安装项目及开发依赖：

```powershell
pip install -e ".[dev]"
```

运行测试：

```powershell
python -m pytest -q
```

检查 Python 源码能否编译：

```powershell
python -m compileall src
```

## Run

```powershell
.\\.venv\\Scripts\\python.exe -m uvicorn embedded_copilot.api.main:app --host 127.0.0.1 --port 8000
```

接口：

- `GET /api/v1/health`
- `POST /api/v1/chat`
- `GET /health`，兼容别名
- `POST /chat`，兼容别名

请求示例：

```json
{
  "message": "ESP32如何配置SPI？"
}
```

响应包含：

- `answer`
- `agents_used`
- `sources`
- `trace_id`
- Agent-specific `result`
- 可空 `error`

## Knowledge Base

服务启动时读取 `knowledge/` 下的 UTF-8 Markdown 和 PDF，执行 chunking、
embedding 与 Chroma indexing。PDF citation 使用 1-based page；Markdown 的
page 为 `null`。

仓库中的 `knowledge/embedded_basics.md` 是原创离线 Seed，仅用于 Foundation
演示。加入真实 Datasheet 前应确认使用授权，并保留 source 与 license 信息。
生成的 Chroma 数据位于 `.data/`，不会提交到 Git。

## Offline Behavior

- Knowledge Agent 只依据检索结果回答；无命中时明确返回未找到。
- Firmware Agent 可离线演示 ESP32 FreeRTOS LED task，并返回结构化代码、解释
  与 limitations；输出不会声称已经通过硬件验证。
- Debug Agent 将 Evidence、Root Cause、Confidence、Recommendation 和
  Next Steps 分开。
- 本地 Hash Embedding 是确定性 v0.1 演示方案，不代表生产检索质量。
- 所有生成代码均未经过编译、烧录或真实硬件验证。
- v0.1 的同步 Retriever/LLM adapter 在线程中执行；Tool timeout 会停止等待并返回
  结构化错误，但不能强制终止已经运行的同步线程。在线 provider 还必须配置自身
  的 request timeout，不能把 Tool timeout 当作底层操作已取消的证明。

配置 `EMBEDDED_COPILOT_RUNTIME_MODE=llm` 后，可通过
`services/llm.py` 的 LangChain adapter 使用 OpenAI-compatible chat model。
必须同时配置 model、base URL（如需要）和 API Key。Embedding provider 也可
单独切换，但默认测试不会调用外部服务。

## Tests

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q
.\\.venv\\Scripts\\python.exe -m pip check
```

测试默认使用 Ephemeral Chroma、deterministic embedding 和 injected fakes。

## Embedded Copilot Architecture

v0.2.1 Foundation 在现有 LangGraph Runtime Agent 架构之外提供稳定的未来扩展接口：

- `BaseAgent`：统一的 typed Agent 抽象。
- `AgentRegistry`：Agent 实例注册与查询。
- `CapabilityRegistry`：领域能力注册框架，不包含具体 Capability。
- `KnowledgeRetriever`：与 Chroma、FAISS 或 Embedding 无关的知识接口。
- `AgentTask`、`AgentResult` 和 `AgentContext`：任务、结果与上下文模型。
- `Settings`：统一的环境变量配置入口，并保留旧导入路径兼容性。

这些接口当前未接入 Supervisor、Agent State 或 LangGraph Workflow。现有 Runtime
Firmware Agent 保持不变。

## Firmware Agent Architecture

v0.5.0 在 Firmware Intelligence pipeline 上增加结构化、确定性的 Firmware Project
Generation Layer：

```text
AgentTask -> Requirement Analyzer -> Knowledge Retriever -> Firmware Planner
          -> FirmwareProjectGenerator -> FirmwareProjectValidator -> AgentResult
```

- `embedded_copilot.agents.firmware.FirmwareAgent`：现有 LangGraph Runtime Agent，
  保持异步接口和原有调用方式。
- `embedded_copilot.firmware.FirmwareAgent`：新的同步 Foundation Agent，提供 Platform
  abstraction、Firmware Knowledge retrieval、deterministic planning、mock Template system、
  project generation interface 和 validation interface。其成功输出为内存中的
  `FirmwareProject` JSON。

Firmware Agent 不会自动读取本地文件。调用方可以显式构建离线知识检索器：

```python
from embedded_copilot.firmware import FirmwareAgent
from embedded_copilot.firmware.knowledge import (
    FirmwareChunker,
    FirmwareDocumentLoader,
    FirmwareKnowledgeRetriever,
)

documents = FirmwareDocumentLoader().load("knowledge/docs")
chunks = FirmwareChunker().chunk(documents)
agent = FirmwareAgent(retriever=FirmwareKnowledgeRetriever(chunks))
```

Project Generator 复用既有 `FirmwareGenerator` 的 mock C 输出，但工程级路径、header、
README 和 build scaffold 只由独立的 project templates/adapters 提供。它不会修改旧
Generator templates 或 bindings。ESP32 工程使用 `main/` 结构；STM32 UART 工程使用
`Core/Src/` 与 `Core/Inc/` 结构。

```python
from embedded_copilot.agents.types import AgentTask
from embedded_copilot.firmware import FirmwareAgent, FirmwareProject

result = FirmwareAgent().run(
    AgentTask(
        task_id="project-demo",
        task_type="firmware",
        requirement="ESP32 ESP-IDF GPIO WiFi",
        metadata={"project_name": "sensor_node"},
    )
)
project = FirmwareProject.model_validate_json(result.output)
```

当前 Project 只存在于返回模型中，不写入本地目录，也不是可编译或经过硬件验证的真实
ESP-IDF/STM32 工程。本阶段不支持 LLM 直接代码生成、SDK 下载、真实编译、自动烧录、
硬件控制、PCB 或 EDA 处理。所有工程内容都明确标记为 mock/unverified。

## Current Runtime Scope

已纳入：

- Supervisor Agent
- Knowledge Agent
- Firmware Agent
- Debug Agent
- RAG
- Tool Calling
- FastAPI
- pytest

未纳入：PCB、KiCad、Altium、EasyEDA、Hardware Agent、Competition Agent、
Edge AI、Computer Use、自动烧录、自动硬件测试、Neo4j、MinIO 和 Milvus。
