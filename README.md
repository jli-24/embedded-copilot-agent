# Embedded Copilot Agent

Embedded Copilot Agent v0.34.0 是面向嵌入式工程师的可追踪工程分析系统。项目将
Multi-Agent workflow、结构化 evidence、知识检索、FastAPI 和 Streamlit 组合为离线可测、
边界清晰的 Engineering Copilot。

## Overview

系统接收工程需求与 metadata-only 附件描述，由 Supervisor 规划已有领域 Agent，最终返回
唯一的跨 API 分析结果 `EngineeringReport`。v0.20.0 新增独立 Evaluation Layer、四视图
Demo、release documentation 和 CI quality gate；不改变已有 Agent workflow 或 API contract。

v0.33.0 新增独立 Workspace Operation Layer，提供可信根快照、严格 diff 验证、外部人工
审批后的受控修改和无内容审计；不接入 Agent、API、UI、Shell、Git、构建或 IDE 控制。

v0.34.0 新增 VS Code MCP Integration Layer，提供 transport-neutral MCP 工具适配契约；
不安装 MCP SDK、不启动 MCP Server。Workspace Runtime 保持唯一写入口，变更 proposal
必须经过同一 Workspace Runtime validation。

当前可分析的领域包括：

- Datasheet analysis
- PCB review
- Firmware analysis
- Debug diagnosis

## Architecture

```text
User / Streamlit
  -> FastAPI
  -> AnalysisService
  -> Supervisor
  -> Knowledge -> Planning -> Agents
  -> EngineeringReport
```

Evaluation 是生产 workflow 外部的同步观察者：

```text
Synthetic BenchmarkDataset
  -> EvaluationRunner
  -> injected Supervisor
  -> EngineeringReport
  -> deterministic metrics
  -> EvaluationReport (JSON / Markdown)
```

它不读取附件文件、不扫描目录、不保存 request 或 `AgentResult`，也不创建缓存、索引或
LLM judge。逐 Agent latency 不可从当前公共边界可靠观测，因此明确标记为 `unavailable`。

## Features

- Supervisor-driven Multi-Agent orchestration
- Local/GitHub Knowledge Provider architecture
- Metadata-only multimodal input foundation
- Deterministic PCB and Datasheet evidence parsing
- Firmware、Hardware、PCB、Debug domain Agents
- Traceable `EngineeringReport` with `source_agent` and `source_id`
- Offline Evaluation metrics and deterministic renderers
- Coding Runtime provides read-only code understanding, static analysis, and build-log analysis.
- Workspace Runtime provides approval-gated existing-text-file modification under a trusted root.
- VS Code MCP Integration Layer provides transport-neutral adapters to existing Runtime Ports.
- FastAPI product API and Streamlit engineering workbench

## Demo

Streamlit 提供四个视图：

- `Overview`：项目定位、workflow 和技术栈
- `Workbench`：通过 FastAPI 提交需求与附件元信息
- `Benchmark`：只展示安全的 release evaluation projection，不执行 benchmark
- `Example Report`：展示经过 schema 验证的 ESP32 Camera 示例报告

启动 API：

```powershell
python -m uvicorn embedded_copilot.api.main:app --host 127.0.0.1 --port 8000
```

启动 Web：

```powershell
python -m streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501
```

默认地址为 `http://127.0.0.1:8501`。Workbench 只上传文件名、MIME、大小、类型等附件
元信息；Web 不读取上传内容，也不绕过 FastAPI 调用 Supervisor 或领域 Agent。

## Benchmark

v0.20.0 默认复用 3 个 synthetic end-to-end integration cases，覆盖 ESP32 Camera、
Firmware/Debug 和 PCB review workflow。内部 Evaluation metrics 包括：

- Task Routing Accuracy
- Agent Success Rate
- Report Completeness
- Evidence Traceability
- Total Execution Latency

质量指标完全由现有 `EngineeringReport` 和 trace 确定性计算。total latency 使用 monotonic
clock 直接观测；逐 Agent latency 不估算。Dashboard 中的 1/2/3 ms 是 fixed-clock 的
deterministic contract snapshot，平均值为 2 ms，不代表真实设备或生产性能。

运行 Evaluation 和相关回归：

```powershell
python -m pytest tests/evaluation tests/benchmark tests/integration -q
```

## Installation

要求 Python 3.11。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

默认 `runtime_mode=offline`，测试不需要真实硬件、串口、在线模型或公网。API Key、Token
和密码只能通过环境配置注入，不得写入仓库。

## Deployment

Docker Compose 同时定义 API 和 Web 服务：

```powershell
docker compose build
docker compose config
docker compose up
```

- API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/api/v1/health`
- Web: `http://127.0.0.1:8501`

若本机没有 Docker，只能视为 Dockerfile/compose 静态结构已验证，不能声称容器已成功运行。

## Engineering Design

核心工程边界：

- API Layer 只做 validation、dependency resolution 和 response mapping。
- `AnalysisService` 是 API 与 Agent workflow 的唯一桥梁。
- Supervisor 只做分析、规划、调度和聚合，不实现领域知识。
- Runtime Agent 的外部能力只能通过 Tool/Knowledge boundary。
- `EngineeringReport` 是分析 API 唯一返回结果，所有工程字段保持 provenance。
- Evaluation 只调用注入的 Supervisor，并只输出统计、计数、安全 ID 和安全 failure code。
- Web 只通过 `ProductApiClient` 发起分析，不 import Runtime Agent implementation。

质量检查：

```powershell
python -m pytest -q
python -m compileall -q src tests
ruff check .
git diff --check
```

## Limitations

- 不自动修改 PCB。
- 不自动烧录设备。
- 不替代 EDA DRC、ERC 或 connectivity verification。
- 不替代人工审核和真实硬件验证。
- Datasheet complex table 无可靠结构时安全失败或忽略，不使用 LLM 猜测。
- PCB/Datasheet parsing 只支持已验证的有限格式和 evidence 范围。
- Evaluation total latency 是本地进程观测值，不是实时性保证；逐 Agent latency 为
  `unavailable`。
- Coding Runtime 不执行构建或 Git、不控制 IDE 或硬件；其硬件/软件输出为未验证候选，需工程师审核。
- Workspace Runtime 不生成 patch，不执行命令、构建或 Git，也不控制 IDE；所有变更必须绑定
  已验证 snapshot、proposal 和外部人工审批。
- VS Code MCP Integration Layer 不包含 MCP SDK、server transport 或真实 VS Code connection；
  Workspace Runtime 保持唯一写入口。
