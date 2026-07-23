# Embedded Copilot Agent

Embedded Copilot Agent v0.8.0 是面向嵌入式开发者的 Foundation Agent
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

## Hardware Design Intelligence Architecture

v0.6.0 新增独立的同步 Foundation Hardware pipeline：

```text
AgentTask -> Hardware Requirement Analyzer -> Hardware Knowledge Retriever
          -> Hardware Planner -> Hardware Validator -> AgentResult
```

`embedded_copilot.hardware.HardwareAgent` 根据自然语言或显式传入的
`FirmwareProject` 返回结构化 `HardwarePlan` JSON。它不接入 Runtime Supervisor 或
LangGraph，也不会自动扫描文件系统。Hardware Knowledge 必须由调用方显式注入：

```python
from embedded_copilot.agents.types import AgentTask
from embedded_copilot.hardware import (
    HardwareAgent,
    HardwareDocument,
    HardwareKnowledgeRetriever,
)

documents = [
    HardwareDocument(
        id="camera-guide",
        title="Authorized Camera Selection Notes",
        category="camera",
        vendor="Example",
        content="Original or authorized hardware notes.",
        metadata={"peripheral": "Camera", "component_name": "Approved module"},
    )
]
agent = HardwareAgent(retriever=HardwareKnowledgeRetriever(documents))
result = agent.run(
    AgentTask(
        task_id="hardware-demo",
        task_type="hardware",
        requirement="ESP32-S3 camera hardware plan",
    )
)
```

具体器件名称只来自显式 metadata 或检索文档 metadata；无证据时仅输出通用、未验证的
组件候选。Hardware pipeline 不生成 PCB、原理图、EDA、BOM、Layout，不下载 Datasheet，且不执行
电气参数自动确定或真实硬件验证。

## PCB Design Intelligence Architecture

v0.7.0 新增独立的同步 Foundation PCB requirement review pipeline：

```text
AgentTask -> PCB Requirement Analyzer -> PCB Knowledge Retriever
          -> PCB Rule Engine -> PCB Reviewer -> PCB Validator -> AgentResult
```

`embedded_copilot.pcb.PCBAgent` 接受自然语言 PCB 描述，或通过
`AgentTask.metadata["hardware_plan"]` 接受 `HardwarePlan` 实例/JSON-compatible dict，
返回结构化 `PCBReviewReport` JSON。知识文档必须由调用方显式注入：

```python
from embedded_copilot.agents.types import AgentTask
from embedded_copilot.pcb import (
    PCBAgent,
    PCBKnowledgeRetriever,
    PCBRuleDocument,
)

documents = [
    PCBRuleDocument(
        id="authorized-layout-notes",
        title="Authorized Layout Review Notes",
        category="communication",
        content="Original or authorized PCB review guidance.",
    )
]
agent = PCBAgent(retriever=PCBKnowledgeRetriever(documents))
result = agent.run(
    AgentTask(
        task_id="pcb-demo",
        task_type="pcb",
        requirement="ESP32 camera SPI PCB review",
    )
)
```

Rule Engine 是确定性、无副作用的 requirement-level evidence checker；稳定 Issue ID
只表示同一条规则，不代表读取了真实 PCB connectivity。当前不支持 PCB 绘制、自动布线、
原理图、EDA/KiCad/Altium 控制、Gerber、BOM、真实工程读取或硬件验证。

## Knowledge Gateway Architecture

v0.8.0 新增同步、确定性、离线优先的统一知识访问层：

```text
KnowledgeQuery -> KnowledgeGateway -> Local / GitHub Mock / Web Mock Providers
               -> validation -> merge -> stable ranking -> KnowledgeResult list
```

Local Provider 只包装现有 Firmware、Hardware 和 PCB Retriever，不修改 Retriever，
也不自动扫描文件系统。Web/GitHub Provider 默认返回空列表，只能由调用方显式注入
exact-query 离线 fixture；它们不会访问网络、GitHub API 或读取 Token。

```python
from embedded_copilot.knowledge.gateway import (
    KnowledgeGateway,
    KnowledgeGatewayAdapter,
)
from embedded_copilot.knowledge.github import GitHubSearchProvider
from embedded_copilot.knowledge.local import LocalKnowledgeProvider
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeSource
from embedded_copilot.knowledge.web import WebSearchProvider

local = LocalKnowledgeProvider()
gateway = KnowledgeGateway(
    [local, GitHubSearchProvider(), WebSearchProvider()]
)
results = gateway.search(
    KnowledgeQuery(
        query="ESP32 SPI",
        sources=[KnowledgeSource.LOCAL],
        top_k=4,
    )
)
adapter = KnowledgeGatewayAdapter(gateway, local, top_k=4)
```

每个 Provider 必须把 `KnowledgeQuery` 当作不可变输入，并最多返回 `query.top_k`
条结果；Gateway 合并后仍会执行全局 top-k。任一 Provider 失败、修改 query、返回超量
或 malformed result 时，Gateway 整体安全失败，不返回不可诊断的部分结果。本阶段不把
Gateway 注入现有 Agents，也不提供真实 Web/GitHub 搜索。

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

未纳入：Runtime PCB Agent、KiCad、Altium、EasyEDA、Runtime Hardware Agent、Competition Agent、
Edge AI、Computer Use、自动烧录、自动硬件测试、Neo4j、MinIO 和 Milvus。
