# Embedded Copilot Agent

Embedded Copilot Agent v0.48.0 是面向嵌入式工程师的可追踪工程分析系统。项目将
Multi-Agent workflow、结构化 evidence、知识检索、FastAPI 和 Streamlit 组合为离线可测、
边界清晰的 Engineering Copilot。

## Overview

v0.48.0 adds a framework-independent, deterministic, proposal-only Optimization
Layer. It converts typed Hardware Observation projections into bounded
mathematical candidates, performs deterministic evaluation, and requires Human
Approval before returning a reviewed immutable result. It provides mathematical
candidate only behavior: no hardware control, no real tuning, and no measurement
capability.

v0.47.0 adds a framework-independent, observation-only Hardware Intelligence
Layer. It combines caller-owned Digital Twin projections, structured Hardware
Observation values, HIL reference projections, approval-bound Validation
Projection, and safe Execution Integration into immutable snapshots. It does not
perform physical hardware control, USB or Serial communication, Flash, Debug,
real HIL execution, or physical hardware validation.

v0.46.0 adds a framework-independent Execution Integration Layer. It converts a
successful Agent Execution Snapshot and reviewed Proposal Projection into a
fingerprinted Execution Plan, binds one exact caller-owned executor, requires a
typed Human Approval proof, verifies the safe result projection, and returns a
terminal Execution Snapshot. The production package provides no real executor and
does not perform Build, Flash, Hardware Debug, Shell, Git, network, filesystem
mutation, or hardware control.

v0.45.0 新增 framework-independent、human-controlled Human Loop Layer，将 metadata-only
Engineering Generation Proposal 显式绑定到 Human Review Lifecycle、Feedback Projection、
Revision Context 和新的 Revision Proposal。该层不自动批准、不修改 Artifact，不调用 Agent 或
Tool，也不执行 Build、Flash、Hardware Debug、Memory write 或 Knowledge mutation。

系统接收工程需求与 metadata-only 附件描述，由 Supervisor 规划已有领域 Agent，最终返回
唯一的跨 API 分析结果 `EngineeringReport`。v0.20.0 新增独立 Evaluation Layer、四视图
Demo、release documentation 和 CI quality gate；不改变已有 Agent workflow 或 API contract。

v0.33.0 新增独立 Workspace Operation Layer，提供可信根快照、严格 diff 验证、外部人工
审批后的受控修改和无内容审计；不接入 Agent、API、UI、Shell、Git、构建或 IDE 控制。

v0.34.0 新增 VS Code MCP Integration Layer，提供 transport-neutral MCP 工具适配契约；
不安装 MCP SDK、不启动 MCP Server。Workspace Runtime 保持唯一写入口，变更 proposal
必须经过同一 Workspace Runtime validation。

v0.35.0 新增 observation-only Embedded Debug Runtime，提供 caller-owned UART、J-Link、
ST-Link 与 GDB source contract、规范化 Debug Snapshot、telemetry 和无内容 audit；不包含
真实设备 transport、Flash、reset、寄存器/内存写入、自动调试、Agent、API 或 UI。
Workspace Runtime 仍是唯一文件写入口。

v0.36.0 新增 deterministic、observation-only Telemetry Intelligence Layer，提供
caller-owned `DEBUG_RUNTIME`/`MOCK` source contract、带 SHA-256 指纹的 sample 与
bounded series，以及确定性统计、endpoint trend 和 `unverified` anomaly candidate；
不包含 PID optimization、automatic tuning、hardware control、Flash、真实 transport、
后台采集、缓存、持久化或硬件验证。

v0.37.0 新增 security-first Tool Execution Layer，提供 request fingerprint 绑定的权限决策、
不可变 capability adapter registry、结果规范化和同步双阶段审计；build/test 仅支持显式
Mock scenario，串口日志只投影一次 Debug Runtime UART snapshot，不包含 Agent 接入、Shell、
真实构建/测试、Flash、硬件控制或文件写入。Workspace Runtime 仍是唯一文件写入口。

v0.38.0 新增 Verification Agent Layer，对 Firmware、Hardware 与 Tool Result 执行确定性
候选验证。`FAIL` 仅表示当前提案未通过验证规则，不表示已确认真实硬件故障；任一 Checker
异常会使整批验证失败，不返回部分结果。该层不执行工具、不自动修复，也不改变 Workspace
Runtime 的唯一写边界。

v0.39.0 新增 Engineering Memory Layer，以 strict frozen contract、revision、operation
receipt 和最小披露权限保存工程记忆候选。只有兼容 Verification 或受限 Human Approval
可以推进可信状态；首版仅提供同步线程安全的 InMemory reference Store，不提供真实持久化、
Agent/LLM/RAG 调用、Tool execution、文件或硬件操作。Workspace Runtime 仍是唯一写边界。

v0.40.0 新增 read-side Memory Intelligence Layer，将 VERIFIED Memory 确定性投影为规划上下文，
并与 Knowledge Gateway 融合。Memory、Knowledge、Fusion 或 context-aware planning 失败时，
Supervisor 使用脱敏 trace 安全降级，不绕过既有 Permission、Audit 或 Verification contract。

v0.41.0 新增 read-only Knowledge Intelligence Layer，提供注入式 Web Research/Datasheet Port、
确定性 Knowledge Verification、带 `KnowledgeProvenance` 的 Verified Evidence、不可变 Knowledge
Graph Snapshot 和只投影 candidate 的 Memory Bridge。Knowledge Graph 只辅助 Planning，不能生成
任务、选择 Agent、构造 `SupervisorPlan` 或触发执行。

v0.42.0 新增 planning-only Agent Workflow Layer，将 caller-owned requirement、可信 Context/Risk
projection、Engineering Planning Agent、Frozen Task DAG、Human Approval、Deterministic Scheduler
和 Progress Events 组合为确定性的工作流准备边界。该 Runtime 不执行任务，也不调用 Tool、构建、
Flash、文件写入或硬件控制能力。

v0.43.0 新增 controlled-execution Agent Execution Layer，将显式 Workflow Task projection、精确
Agent Registry binding、typed Agent boundary、Verification projection 和 fail-safe Execution Snapshot
组合为受控执行边界。失败执行最多允许一次两阶段人工恢复，不自动重试、不调用 Tool Runtime，
也不执行 Build、Flash 或 Hardware Debug。

v0.44.0 新增 framework-independent、approval-controlled Engineering Generation Layer，
将已验证的 Workflow Task 与 Agent Execution Result 显式投影为可审查的工程 Artifact
Proposal。该层只生成结构化提案和 Approved Artifact Reference，不写入工程文件、不调用
Tool Runtime，也不执行 Build、Flash、Hardware Debug 或真实 PCB 生成。

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

## v0.48 Optimization Layer

```text
Hardware Observation Projection
  -> Optimization Plan
  -> Unverified Optimization Proposal
  -> Deterministic Evaluation Projection
  -> Human Approval
  -> Reviewed Optimization Result
```

The Optimization Runtime uses exact registry binding and deterministic PID,
Power, and Performance mathematical models. Proposals remain explicitly
unverified until deterministic evaluation and Human Approval are complete.
Approval reviews a mathematical candidate only; it does not execute an action,
control hardware, perform real tuning, or measure a device.

## v0.48 Highlights

- Optimization Runtime
- exact registry binding with no fallback
- PID mathematical candidate projection
- Power mathematical model
- Performance mathematical model
- Deterministic Evaluation Projection
- Human Approval binding
- process-local Replay Protection
- Security Boundary

## v0.47 Hardware Intelligence Layer

```text
SUCCESS ExecutionSnapshot
  -> safe Hardware Context Projection
  -> Digital Twin Boundary
  -> structured Hardware Observation
  -> HIL Projection Boundary
  -> approval-bound Validation Projection
  -> immutable Hardware Intelligence Snapshot
```

The Hardware Intelligence Runtime accepts only caller-owned typed projection
ports. Execution Integration projects safe identifiers from a verified execution
snapshot without reading artifact bodies. A validated projection is software
evidence only and is not a claim of physical hardware validation.

## v0.47 Highlights

- Hardware Intelligence Runtime
- Digital Twin Boundary
- HIL Projection Boundary
- Hardware Observation
- Validation Projection
- Execution Integration
- Deterministic fingerprint binding
- Content-safe progress events
- Security Boundary

## v0.46 Architecture

```text
SUCCESS AgentExecutionSnapshot + ProposalProjection
  -> ExecutionPreparationRequest
  -> Execution Plan
  -> exact Executor Registry Boundary
  -> READY ExecutionSnapshot
  -> Human Approval Binding
  -> Controlled Execution Lifecycle
  -> Verification Projection
  -> terminal ExecutionSnapshot
```

Executor selection is explicit and exact. Human Review approval binds the READY
snapshot and proposal before the process-local single-use execution boundary is
consumed. Failure paths return sanitized terminal snapshots; invalid contracts,
binding mismatches, replay, and progress-delivery failures fail closed.

## v0.46 Highlights

- Execution Runtime
- Executor Registry Boundary
- Execution Plan
- Human Approval Binding
- Controlled Execution Lifecycle
- Verification Projection
- Failure Snapshot
- Replay Protection
- Progress Event Isolation
- Security Boundary

## v0.45 Architecture

```text
Engineering Generation Proposal
  -> metadata-only Proposal Projection
  -> Human Review Lifecycle
  -> APPROVED / CHANGES_REQUESTED / REJECTED
  -> Feedback Projection
  -> Revision Context
  -> Revision Proposal Boundary
  -> Human Review again
```

Human Loop Runtime 只处理 typed、fingerprinted projection。人工决策不会执行修改；结构化
feedback 不被解释为命令，revision 也不会覆盖原始 Artifact，而是形成必须重新进入人工审核的
新 proposal。Progress event 仅包含状态和 caller-provided timestamp，交付失败时 fail closed。

## v0.45 Highlights

- Human Loop Runtime
- Human Review Lifecycle
- Metadata-only Proposal Projection
- Feedback Projection
- Revision Context
- Revision Proposal Boundary
- Progress Event Isolation
- Security Boundary

## v0.44 Architecture

```text
Requirement
  -> Workflow
  -> Agent Execution
  -> Engineering Generation
  -> Artifact Proposal
  -> Verification
  -> Human Approval
```

Generator 通过显式 Registry capability binding 注入；Runtime 不扫描模块、不自动 fallback，
也不持有 generator lifecycle。所有 Hardware、Firmware、PCB 与 BOM 输出均为带指纹、待验证、
待人工审批的结构化 proposal，不代表真实工程文件或硬件结果。

## v0.44 Highlights

- Engineering Generation Runtime
- Generator Registry Boundary
- Hardware Design Proposal
- Firmware Proposal
- PCB Design Proposal
- BOM Proposal
- Artifact Verification Boundary
- Human Approval Boundary
- Security Isolation

## v0.43 Architecture

```text
Workflow Task
  -> Execution Adapter
  -> AgentExecutionRequest
  -> Agent Registry
  -> Agent Capability Binding
  -> Agent Execution Boundary
  -> Verification Projection
  -> Execution Snapshot
```

Agent type、execution ID、context references、constraints 和 timestamp 均由调用方显式提供；
Runtime 不从任务文本推断 Agent，也不持久化 capability port、prompt、reasoning 或 raw output。

## v0.43 Highlights

- Controlled Agent Execution Runtime
- Explicit Agent Registry Binding
- Execution Lifecycle State Machine
- Safe Result Projection
- Verification Boundary
- Fail-safe Execution Snapshot
- Two-phase Human Resume
- Progress Event Isolation
- Security Boundary

## v0.42 Architecture

```text
Requirement Agent Port
  -> Requirement Specification
  -> Workflow Context Projection
  -> Risk Projection Boundary
  -> Engineering Planning Agent
  -> Frozen Task DAG
  -> Human Approval
  -> Deterministic Scheduler
  -> Progress Events
```

`WorkflowContextPort` 是外部 composition boundary；Knowledge、Memory 和未来 Project Context
adapter 可以在其后组合，但 Workflow Runtime 只接收安全的 `WorkflowContextProjection`。
Risk 仅供 Planning visibility、人工审批和 progress/reporting 使用，不改变 task priority、
scheduling order、DAG dependency 或 Agent selection。

## v0.42 Highlights

- Requirement Agent Port
- Workflow Context Projection
- Risk Projection Boundary
- Engineering Planning Agent
- Frozen Task DAG
- Human Approval
- Deterministic Scheduler
- Progress Events
- Security Boundary

## v0.41 Architecture

```text
External Knowledge Source
  -> Knowledge Candidate Evidence
  -> Knowledge Verification
  -> Verified Knowledge Evidence
  -> Knowledge Graph Projection
  -> Supervisor Planning Context
  -> Engineering Memory Bridge
```

Knowledge 是可选增强来源，不是决策中心。只有 VERIFIED evidence 可以进入 Planning、Graph 或
Memory Bridge。Graph query 只返回 evidence projection；Memory Bridge 不调用
`EngineeringMemoryPort.execute()`，永久规则仍由既有 Permission、Audit、Verification 和人工
审批边界控制。本版本不提供 Neo4j、内置 browser/HTTP transport、自动 PDF 下载、自主搜索循环
或自动 Memory mutation。

## v0.41 Highlights

- Knowledge Intelligence Runtime
- Web Research Source Port
- Datasheet Typed Projection
- Knowledge Verification
- Knowledge Provenance
- Immutable Knowledge Graph Snapshot
- Memory Bridge Projection
- Supervisor Verified-only Planning

## v0.40 Architecture

```text
User
  |
  v
Supervisor Agent
  |
  v
Knowledge Gateway
  |-- RAG
  |-- Engineering Memory
  `-- Context Fusion
  |
  v
Planning Context
  |
  v
Engineering Agents
  |-- Hardware
  |-- Firmware
  |-- PCB
  `-- Debug
  |
  v
Verification
  |
  v
Runtime Execution
```

v0.40 的 Engineering Memory 是 read-side enhancement：仅将已验证记忆投影为确定性的
规划上下文，并与 Knowledge Gateway 结果融合。LLM 和 Agent 不能直接修改 Memory、文件或
工程状态；Workspace Runtime 仍是唯一文件写边界。

## v0.40 Highlights

- Multi-Agent Engineering Workflow
- Memory-Augmented Reasoning
- Knowledge Fusion
- Failure-safe Supervisor
- Security Boundary
- Regression Validation

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
- Engineering Memory separates CANDIDATE records from deterministic VERIFIED projections.
- Knowledge Intelligence projects verified evidence, provenance, graph snapshots, and reviewable memory candidates.
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
