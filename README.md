# Embedded Copilot Agent

Embedded Copilot Agent v0.19.0 是面向嵌入式开发者的 Foundation Agent
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

另一个终端启动产品演示界面：

```powershell
.\\.venv\\Scripts\\python.exe -m streamlit run web/app.py --server.port 8501
```

浏览器访问 `http://127.0.0.1:8501`。Streamlit 通过
`EMBEDDED_COPILOT_API_URL` 连接 FastAPI，默认值为 `http://127.0.0.1:8000`。

接口：

- `GET /api/v1/health`
- `POST /api/v1/chat`
- `POST /api/v1/analyze`
- `GET /api/v1/status/{execution_id}`
- `GET /api/v1/report/{execution_id}`
- `GET /health`，兼容别名
- `POST /chat`，兼容别名

## Product Demo

v0.19.0 增加 metadata-only 产品入口。`POST /api/v1/analyze` 只接收需求文本、
`UserAttachment` 元信息与可选 Agent 列表，返回进程内 `execution_id`；执行状态按
`queued -> running -> completed | failed` 转换。`AnalysisService` 是 API 与同步
Supervisor workflow 的唯一桥梁，最终跨 API 返回的分析结果只有 `EngineeringReport`。

`ExecutionRegistry` 默认最多保存 100 条状态或报告，不保存 request 原文、附件元信息、
`AgentResult`、PCB/Datasheet model 或文件内容。服务必须使用单个 API worker；重启会丢失
执行记录。默认分析超时为 120 秒，超时不会被解释为底层同步线程已被强制终止。

Streamlit 不导入 Supervisor、Agent、Parser 或 Knowledge Gateway。上传控件只读取
filename、MIME 与 size，不调用上传对象的内容读取接口。`demo/esp32_camera/manifest.json`
描述合成 ESP32 Camera 示例；“Load Demo”只加载 manifest 中的需求和附件元信息，四个
fixture 的内容不会进入分析流程。缺少内容证据的领域允许安全失败，UI 不补写结论。

Docker 使用一个 image 和两个 Compose service：

```powershell
docker compose up --build
```

FastAPI 暴露在 `8000`，Streamlit 暴露在 `8501`。Compose 固定 FastAPI 为一个 worker，
不包含认证、数据库、Redis、Celery 或其他消息队列。

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

## Embedded Copilot Integration

v0.18.0 在同步 Foundation Supervisor 内部增加 deterministic Integration Layer：

```text
AgentTask + UnifiedInputContext
  -> SupervisorRequirementAnalyzer
  -> IntegrationPlanner [Agent selection only]
  -> KnowledgeGateway [Supervisor-owned, optional]
  -> SupervisorPlanner
  -> AgentExecutor -> existing AgentDispatcher
  -> validated domain Agent results
  -> immutable content-safe evidence snapshots
  -> ResultAggregator [evidence aggregation only]
  -> EngineeringReport
```

`IntegrationPlanner` 只根据 request、输入文本与附件安全元信息选择 Agent，不产生工程结论。
执行顺序固定为 `FirmwareAgent -> HardwareAgent -> PCBAgent -> DebugAgent`，保留已有
`FirmwareProject -> HardwareAgent` 与 `HardwarePlan -> PCBAgent` handoff。`AgentExecutor`
只委托既有 Dispatcher 并验证返回类型，原 Agent output 原样保留给 legacy Supervisor 路径；Integration
另行创建不含正文和 mutable metadata 的 evidence snapshot，单 Agent 失败不会阻止后续 Agent。

`EngineeringReport` 通过 Supervisor `AgentResult.metadata["engineering_report"]` 暴露，原
`AgentResult.output` 仍是 `SupervisorResult` JSON。报告 section、finding、recommendation 和
trace 都包含 `source_agent` 与 `source_id`。Aggregator 只聚合 snapshot 中已有 Agent evidence 和已有 PCB/
Debug recommendation；Firmware section 只列平台、框架、structure 与相对文件路径，不包含源码。
报告也不会包含 `UnifiedPCBModel`、`UnifiedDatasheetModel`、PDF 正文、PCB 原始数据、日志全文、
绝对路径、Token 或 Knowledge document content。

Integration 不读取附件、不调用 Parser、不持有 Gateway、不增加 Provider、LLM、网络、缓存、索引
或临时文件。预解析 PCB/Datasheet model 在 `EngineeringContext` 中是可选的 validated input；
v0.18 不新增生产注入入口。v0.17 的 Parser 与 Adapter 实现保持不变。

## Datasheet Intelligence

v0.17.0 新增独立、只读的 Datasheet 结构解析链。`InputLoader` 仍只读取附件元信息；
调用方使用显式 attachment-id 到可信根目录相对路径的映射，将 `.md` 或文本型 `.pdf`
交给 Datasheet Parser。Parser 只输出 immutable `UnifiedDatasheetModel`，不调用 LLM、OCR、
网络、旧 `multimodal/` processor 或 RAG loader，也不创建缓存、索引或临时内容文件。

Datasheet Adapter 将结构化 component、pin、interface 和 electrical evidence 转换为现有
`HardwareDocument`、`PCBRuleDocument` 和 `FirmwareDocument`。调用方通过现有 retriever
constructor 注入领域 Agent；Adapter 不执行自动选型，Agent API、Supervisor、Knowledge
Gateway、Provider Contract 与领域输出 schema 保持不变。复杂 PDF 表格若无法从文本行可靠
识别，会被忽略或安全拒绝，不进行几何重建或猜测。

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

v0.13.0 在 v0.8.0 统一知识访问层上增加显式 Provider lifecycle 与本地 snapshot：

```text
KnowledgeQuery
  -> KnowledgeGateway
  -> ProviderRegistry
  -> Local / GitHub Fixture / Web Fixture Providers
  -> candidate merge
  -> Gateway ranking + deduplication + global top-k
  -> KnowledgeResult list
```

`KnowledgeProvider` 保持 runtime-checkable structural `Protocol`，第三方实现不需要继承项目
基类。`ProviderRegistry` 只负责 Provider 注册顺序、生命周期、source filter、query mutation
检查、结果验证和 candidate 合并；返回顺序固定为 Provider 注册顺序及 Provider 内部顺序。
Registry 不执行 ranking、deduplication、source priority 或 top-k。上述检索策略只属于
`KnowledgeGateway`。

Local Provider 支持两种互斥模式：无 root 时保留 v0.12 的 Firmware、Hardware、PCB
Retriever adapter 和 `add_documents()`；显式传入 `knowledge_root` 时，构造阶段一次性读取
`firmware/`、`hardware/`、`pcb/`、`debug/` 下的 `.md` 与 standalone `.json`，形成只读
snapshot。它不自动使用仓库路径或 Settings。Provider score 只作为 candidate 字段，不触发
Provider 内排序。Web/GitHub Provider 仍仅是显式离线 fixture，不访问网络、GitHub API 或 Token。

```python
from embedded_copilot.knowledge.gateway import (
    KnowledgeGateway,
    KnowledgeGatewayAdapter,
)
from embedded_copilot.knowledge.github import GitHubSearchProvider
from embedded_copilot.knowledge.local import LocalKnowledgeProvider
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeSource
from embedded_copilot.knowledge.web import WebSearchProvider

local = LocalKnowledgeProvider(knowledge_root="authorized-knowledge")
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

每个 Provider 必须把 `KnowledgeQuery` 当作不可变输入，可以返回超过 `query.top_k` 的合法
candidates，但不得自行重排或截断统一结果。Gateway 在合并后执行一次全局 ranking、dedup 和
top-k。任一 Provider 失败、修改 query 或返回 malformed result 时，Gateway 整体安全失败，
不返回不可诊断的部分结果。v0.13.0 不新增在线 Provider、HTTP、GitHub API、Datasheet 下载、
LLM 或 LangGraph Runtime。

## Multimodal Input Foundation

v0.15.0 新增独立的 metadata-only 工程输入层：

```text
trusted root / relative file
  -> InputLoader metadata validation
  -> UserAttachment
  -> UnifiedInputContext
  -> attach_input_context()
  -> AgentTask
  -> SupervisorRequirementAnalyzer
  -> SupervisorTask.input_context
  -> existing text-based routing
```

`InputLoader` 只通过文件系统 metadata 获取 basename、extension、size 和受控类型，不打开、
读取、复制、缓存、解析或索引文件内容。Loader 拒绝绝对路径、path traversal、越界路径、
symlink、非普通文件、空文件、超限文件、未知扩展名和不匹配的 MIME；返回模型和安全错误都
不包含真实路径、用户目录、临时目录或文件内容。

```python
from pathlib import Path

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.input import InputLoader, UnifiedInputContext
from embedded_copilot.input.adapters import attach_input_context
from embedded_copilot.supervisor import SupervisorAgent

loader = InputLoader(Path("uploads"))
attachment = loader.load(
    "board.kicad_pcb",
    attachment_id="board-1",
    content_type="application/x-kicad-pcb",
)
context = UnifiedInputContext(
    text="Review this ESP32 PCB layout",
    attachments=(attachment,),
)
task = attach_input_context(
    AgentTask(
        task_id="board-review",
        task_type="routing",
        requirement=context.text,
    ),
    context,
)
result = SupervisorAgent().run(task)
```

`attach_input_context()` 是 context 进入 Supervisor 的唯一公开入口。`AgentTask` schema 保持
不变，Analyzer 消费私有 envelope 后生成内部 `SupervisorTask.input_context`；Planner、
Dispatcher、FirmwareAgent、HardwareAgent、PCBAgent、DebugAgent、KnowledgeGateway 和
Provider 均不接收 `UserAttachment`。

现有 `embedded_copilot.multimodal` 是早期内容处理实现，会读取文本并解析 PDF/图片，不属于
v0.15 安全输入链路，后续版本仍不调用、不迁移也不修改它。Input Layer 不包含 Vision、OCR、
PDF/Datasheet 解析、EDA 内容解析、LLM 总结或文件内容理解。

## PCB Intelligence Foundation

v0.16.0 在 Input Layer 之外新增独立、只读的 KiCad PCB 结构解析链：

```text
InputLoader -> UserAttachment(type=EDA)
            -> RootedPCBSourceResolver
            -> KiCadPCBParser
            -> UnifiedPCBModel
            -> attach_pcb_model()
            -> PCBAgent
            -> PCBReviewReport
```

`PCBSourceResolver` 通过 attachment id 显式映射可信 root 下的相对目标，Parser 不扫描目录，只
读取该 attachment 对应的单个 `.kicad_pcb` 文件。Parser 使用有 size、token 和 nesting-depth
上限的 S-expression 子集解析器，提取 component、pin、net、layer、track、via 和基础 zone；
不修改 EDA 文件，不保存原始内容或 AST，不创建缓存、索引、中间文件，也不访问 Agent、
Supervisor、Knowledge Gateway 或网络。

`UnifiedPCBModel` 是唯一 PCB 结构交换模型，所有 collection 和 nested model 均不可变，metadata
在 deep-copy 后限制为只读 scalar。结构规则只产生确定性 evidence；`pcb.adapters` 再把 evidence
映射为稳定的 `PCBRuleEvaluation`，通过私有 envelope 交给保持原签名的 `PCBAgent.run(task)`。
旧 text-only 和 HardwarePlan 调用继续工作，`PCBReviewReport` JSON schema 不变。

该能力不是 KiCad 完整规范实现，也不包含 Vision、OCR、LLM PCB 判断、自动布线、EDA 写回或
DRC 替代。解析不完整或不受支持的输入会安全失败；报告中的结论必须在 EDA 工具和真实工程
环境中独立验证。

## GitHub Engineering Knowledge Provider

v0.14.0 新增显式注入、同步且完全离线可测的 GitHub engineering knowledge Provider：

```text
KnowledgeQuery -> KnowledgeGateway -> ProviderRegistry
               -> GitHubKnowledgeProvider -> GitHubClient
               -> ordered candidates
               -> Gateway ranking / deduplication / global top-k
```

`GitHubClient` 是 structural `Protocol`，repository、code、issue 和 release raw models
只存在于 `embedded_copilot.knowledge.github` 内部模块，不向 Supervisor、Agent 或 knowledge
package root 导出。`FakeGitHubClient` 只返回显式 synthetic fixtures 的 deep copies；本版本不提供
HTTP client，不读取环境变量、Settings、Token 或全局配置。

```python
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.github.client import FakeGitHubClient
from embedded_copilot.knowledge.providers.github import GitHubKnowledgeProvider

client = FakeGitHubClient(repositories={"ESP32": [synthetic_repository]})
gateway = KnowledgeGateway([GitHubKnowledgeProvider(client)])
```

Provider 根据显式 `github_types`、Supervisor domains 或固定关键词规则选择 client 方法，按
repository、code、issue、release 顺序合并 candidates。它不排序、不去重、不执行 top-k；
统一检索策略仍只属于 Gateway。映射内容使用 whitespace normalization 后固定截断至 2000
字符，不调用 LLM，不保存完整源码或完整 issue/release 正文。Reference URL 仅允许无 query、
fragment 或 userinfo 的 GitHub repository、issue 和 release HTTPS 路径。

未注入 client 时 Provider 返回空 candidates，Gateway 与 Supervisor 继续正常执行。Rate limit
及其他 client failure 只返回固定安全错误，不公开 Token、header、URL query、路径或异常正文。
现有 `GitHubSearchProvider` 离线 fixture import 保持兼容。v0.14.0 不执行真实 GitHub API、
HTTP、网页抓取、clone、下载、缓存、数据库、LLM 或 LangGraph Runtime。

## Supervisor Foundation Architecture

v0.9.0 新增独立的同步、确定性 Foundation Supervisor pipeline：

```text
AgentTask -> SupervisorRequirementAnalyzer -> SupervisorPlanner
          -> AgentDispatcher
          -> FirmwareAgent -> HardwareAgent -> PCBAgent
          -> SupervisorResultAggregator -> AgentResult
```

新 Supervisor 只负责规则分析、固定顺序规划、本地显式注册、顺序调度、类型化
handoff 和结果聚合。它不调用 LLM，也不会自动查询 `KnowledgeGateway`：

```python
from embedded_copilot.agents.types import AgentTask
from embedded_copilot.supervisor import SupervisorAgent

result = SupervisorAgent().run(
    AgentTask(
        task_id="system-demo",
        task_type="system_design",
        requirement="ESP32-S3 camera firmware, hardware and PCB design",
    )
)
```

也可以从 `embedded_copilot.supervisor.agent` 导入同一个 `SupervisorAgent`。现有
`embedded_copilot.agents.supervisor` 仍是 LangGraph Runtime routing module，导入路径
和行为保持不变，两者不会互相 shadow。

Dispatcher 在每次调用前创建包含嵌套 metadata 的独立深拷贝，并生成
`<parent_task_id>:<agent_name>` 子任务 ID。领域 Agent 对任务副本的修改不会反向写回
原始 `AgentTask`、`SupervisorTask`、`SupervisorPlan`，也不会污染后续 Agent。

成功输出按以下契约重新验证并通过 JSON-compatible 独立副本传递：

- `FirmwareProject` 从 Firmware handoff 到 Hardware。
- `HardwarePlan` 从 Hardware handoff 到 PCB。
- `PCBReviewReport` 在 PCB 完成时验证。

malformed `SUCCESS` 会被转换为安全的 `SupervisorDispatchError` 结果，不参与 handoff；
既定计划中的后续 Agent 仍从原始 request 继续执行。任一领域任务、dispatch 或 handoff
失败时，顶层状态为 `AgentStatus.ERROR`，但 `output` 仍保留可解析的完整
`SupervisorResult`，其中包含按计划排序的 completed、failed 和完整 `AgentResult`
envelope。

当前实现不包含并行、重试、Agent loop、动态增删计划、自动知识检索、文件系统访问或
网络访问，也不接入现有 LangGraph Workflow、`AgentState`、FastAPI route 或 HTTP schema。

## Debug Intelligence Architecture

v0.10.0 新增独立、同步、确定性的 Foundation Debug pipeline：

```text
AgentTask -> DebugRequirementAnalyzer -> DebugKnowledgeRetriever
          -> DebugAnalyzer -> DebugPlanner -> DebugReport assembly
          -> DebugValidator -> AgentResult
```

`embedded_copilot.debug.DebugAgent` 与
`embedded_copilot.debug.agent.DebugAgent` 指向同一个同步 Foundation Agent；现有
`embedded_copilot.agents.debug.DebugAgent` 仍是独立的异步 Runtime Agent，未被替换或接入。

输入为 `AgentTask`。Requirement Analyzer 只规范化 ESP32/STM32 platform、五类 canonical
error type 与日志行；输出为 `DebugReport` JSON，包含确定性 summary、bounded evidence、
findings、recommendations 和不含知识正文的 provenance metadata。无法安全分类时返回错误，
不会生成 `unknown` 成功报告。

知识检索默认关闭且不会自动构造 `KnowledgeGateway`。如需知识增强，调用方必须显式注入只接收
string query 的 `search()` 或 `retrieve()` adapter，例如：

```python
from embedded_copilot.agents.types import AgentTask
from embedded_copilot.debug import DebugAgent
from embedded_copilot.debug.knowledge import DebugKnowledgeRetriever
from embedded_copilot.knowledge.gateway import KnowledgeGatewayAdapter

adapter = KnowledgeGatewayAdapter(gateway, local_provider)
agent = DebugAgent(retriever=DebugKnowledgeRetriever(adapter))
result = agent.run(
    AgentTask(
        task_id="debug-demo",
        task_type="debug",
        requirement="ESP32 task watchdog reset",
    )
)
```

Debug query 只包含 canonical platform、error type 和 allowlisted diagnostic keywords，不会把
完整日志发送给知识层。知识结果只能补充来源与建议，不能在缺少输入/log signature 时独立制造
Finding。没有知识命中时仍可生成规则报告，但会标记
`analysis_mode="unverified_rule_based"`。

该 pipeline 仅提供离线工程辅助，不调用 LLM，不访问文件系统或网络，不修改代码，不执行自动
修复、编译、烧录，也不控制 GDB/JTAG、设备或实时硬件调试。输出不代表唯一 Root Cause，且未经
真实构建、设备测量或硬件验证。v0.10.0 未修改 Supervisor、Runtime LangGraph、API routes、
Tools 或 RAG，也不会自动注册到 Supervisor。

## Supervisor × Knowledge Gateway Integration

v0.12.0 为同步 Foundation Supervisor 增加集中式知识调度：

```text
AgentTask
  -> SupervisorRequirementAnalyzer
  -> KnowledgeQueryBuilder
  -> KnowledgeGateway
  -> KnowledgeContext
  -> SupervisorPlanner
  -> AgentDispatcher + knowledge adapters
  -> Firmware / Hardware / PCB / Debug
  -> SupervisorResultAggregator
```

`KnowledgeGateway` 只通过 `SupervisorAgent` 构造参数显式注入。Gateway invocation
ownership belongs exclusively to `SupervisorAgent.run()`；Planner、Dispatcher、知识 adapter
和领域 Agent 均不会持有或再次调用 Gateway。每次 Supervisor run 最多检索一次，不重试，
并在调用前后检查 `KnowledgeQuery` 是否被修改。

Supervisor 层 adapter 将 `KnowledgeResult` 转换为 `FirmwareDocument`、
`HardwareDocument`、`PCBRuleDocument` 或 `DebugEvidence`，Dispatcher 只向 child task
注入相应领域数据、安全 provenance 和 `knowledge_mode="supervisor_gateway"`。领域 Agent
不导入 `KnowledgeContext`、`ExecutionContext` 或其他 Supervisor 模型。某领域没有命中时，
空知识仍是合法集中式输入，不会回退到本地 retriever；未注入 Gateway 时则完整保留 v0.11
的本地检索路径。

显式 Gateway 路径提供 allowlisted Supervisor trace：`task_parsed`、
`knowledge_query_built`、`gateway_retrieved`、`context_built`、`agent_routed` 和
`finished`。Trace 不包含查询、知识正文、原始日志、异常正文、路径、token 或凭据；内部
`execution_id` 也不会进入公开结果。本版本没有新增 Provider、HTTP、GitHub API、下载、
LLM 或 LangGraph Runtime，四个领域输出和 Benchmark 公共契约保持不变。

## Benchmark Evaluation & Regression Architecture

v0.11.0 新增独立、同步、离线且确定性的外部评估层：

```text
Synthetic BenchmarkDataset -> BenchmarkRunner -> Explicitly Injected Targets
                           -> TraceCollector -> BenchmarkEvaluator
                           -> BenchmarkReportBuilder -> BenchmarkReport
                           -> BenchmarkBaseline / RegressionComparator
```

`embedded_copilot.benchmark.BenchmarkRunner` 只调用使用方显式注入的
`SupervisorAgent`、Foundation Agent 或 `KnowledgeGateway`。Benchmark 不创建 Agent、
不修改 Agent 行为、不写入 `AgentRegistry`、不接入 Supervisor 或 LangGraph，也不改变
API、Tools、RAG 或生产执行路径。导入 package 只公开 `BenchmarkRunner`，不会导入或初始化
Runtime Agents、Workflow、API、production Registries、datasets 或 CLI。

Golden Dataset 通过 `embedded_copilot.benchmark.datasets.synthetic` 显式创建，只包含
synthetic fixtures，不读取文件路径或扫描目录，也不包含真实文档、源码、设备日志、私有信息
或在线派生数据。Runner 顺序执行，每个 case 只调用一次；case 级失败被隔离为安全的零分结果，
不会把原始输入、Agent output、生成代码、Debug 日志、知识正文、traceback、凭据或机器路径写入
`BenchmarkResult`/`BenchmarkReport`。

确定性指标覆盖 Foundation routing、Firmware、Hardware、PCB、Debug、Knowledge 和
end-to-end pipeline。Knowledge 评估包含 hit rate、source accuracy、ranking accuracy、
Recall@K 和 MRR；Trace 只观察 Supervisor 已返回的 plan/results metadata，用于 completion 与
handoff 评分，不回调 Supervisor。执行时间和原始 Trace 不进入 Report，因此报告及其 hash
可稳定复现。

`BenchmarkBaseline` 同时记录 `benchmark_version`、`evaluated_project_version`、
`schema_version`、`report_hash` 和 `metrics_hash`。Regression comparison 在 schema version
不兼容时明确拒绝，不进行隐式迁移。Baseline 与 Report 只存在于内存中的显式调用结果，
本模块不自动持久化或扫描历史数据。

`python -m embedded_copilot.benchmark.run` 是预留 CLI 边界，当前固定返回状态码 2，
不提供 Dataset I/O。该评估层不使用 LLM judge，不访问网络，不生成训练数据，不执行模型优化，
也不构成真实构建、设备或硬件验证。

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
