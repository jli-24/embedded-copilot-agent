# Embedded Copilot Project Context

# 0. Project History Before v0.26

## Early Stage: Agent Foundation

v0.1 - v0.10

目标：

验证 Embedded Copilot 基础方向。

主要探索：

- 嵌入式工程知识助手
- RAG 知识库
- Multi-Agent 架构
- Datasheet 理解
- 硬件/软件工程场景分析

阶段成果：

建立：

- Agent 基本流程
- 工程知识检索
- 嵌入式领域任务模型

---

## Engineering Intelligence Prototype

v0.11 - v0.20

目标：

从普通 AI 助手向工程智能助手演进。

主要能力：

- 嵌入式知识理解
- 文档分析
- Datasheet 探索
- 工程上下文管理
- 初步多模态输入

探索：

- Firmware Agent
- Hardware Agent
- Debug Agent
- PCB 相关能力

---

## Architecture Refactoring Phase

v0.21 - v0.25

目标：

解决早期 Agent 架构耦合问题。

发现问题：

早期：

```text
User
  ↓
Agent
  ↓
Tool
```

存在：

- Agent 权限过大
- 工具边界不清
- 状态不可控
- 难以验证

因此开始重构：

从：

> Agent-centric

转向：

> Runtime-centric Architecture

形成核心原则：

- Runtime != Agent
- Protocol First
- Security Boundary First
- Deterministic Engineering

---

## v0.26 Model Runtime

项目进入正式 Multi-Runtime Architecture。

建立：

```text
Conversation
  ↓
ReasoningPort
  ↓
ModelRuntime
  ↓
Provider
```

之后所有 Runtime 均遵循：

- framework-independent
- Protocol-based
- Frozen DTO
- Capability isolation

# 1. Project Identity

Embedded Copilot 是基于 Multi-Runtime Architecture 的嵌入式研发智能助手。

项目定位：

> Engineering Reasoning Platform

长期目标是覆盖完整的嵌入式工程链路：

```text
需求分析
  ↓
Datasheet 理解
  ↓
Engineering Context Fusion
  ↓
Reasoning
  ↓
Coding
  ↓
Workspace
  ↓
Debug
  ↓
Telemetry
  ↓
Tool Execution
  ↓
未来 Hardware Optimization
```

Embedded Copilot 不是简单 ChatBot，也不是单一 Agent，而是由 Runtime、Agent
和 Tool 共同组成的工程平台。

# 2. Current Status

- Current Version：v0.38.0
- Latest Completed：v0.38.0 Verification Agent Layer
- Latest Commit：`b9498ea68867a169065a14bc5eb9f300ea1c7269`
- Current Tag：`v0.38.0`
- Next Version：v0.39.0 Engineering Memory Layer

Previous tags：

- v0.26.0 Model Runtime
- v0.27.0 Vision Runtime
- v0.28.0 Secure File Runtime
- v0.29.0 Datasheet Intelligence
- v0.30.0 Engineering Context Fusion
- v0.31.0 Reasoning Intelligence Layer
- v0.32.0 Coding Intelligence Layer
- v0.33.0 Workspace Operation Layer
- v0.34.0 VS Code MCP Integration Layer
- v0.35.0 Embedded Debug Runtime
- v0.36.0 Telemetry Intelligence Layer
- v0.37.0 Tool Execution Layer
- v0.38.0 Verification Agent Layer

# 3. Architecture Overview

```text
User
  ↓
VS Code / Future Agent
  ↓
Reasoning Runtime
  ↓
Coding Runtime
  ↓
Workspace Runtime
  ↓
Tool Runtime
  ↓
Engineering Result
  ↓
Verification Agent
  ↓
PASS / FAIL / REVIEW_REQUIRED
  ↓
Debug / Telemetry / Hardware Observation
```

每个 Runtime 保持独立，通过公开 Port / Protocol 通信。上层调用方只依赖稳定
contract，不直接访问其他 Runtime 的内部实现或具体 adapter。

# 4. Completed Runtime List

## Model Runtime

职责：模型能力抽象。

## Vision Runtime

职责：安全视觉输入。

## File Runtime

职责：安全文件读取。

## Datasheet Runtime

职责：Datasheet 结构分析。

## Context Runtime

职责：多来源上下文融合。

## Reasoning Runtime

职责：确定性工程推理。

## Coding Runtime

职责：代码理解、构建分析、Diff 分析。

## Workspace Runtime

职责：唯一文件修改入口。

## VSCode Runtime

职责：MCP Integration Layer。

## Debug Runtime

职责：硬件观察。

## Telemetry Runtime

职责：数据分析与趋势检测。

# 5. Core Design Principles

- Runtime != Agent
- Observation != Control
- Hardware Read != Hardware Mutation
- Workspace Runtime is the only write boundary
- Protocol First
- Frozen DTO
- Deterministic Behavior
- Security Boundary First
- LLM cannot directly control engineering state

# 6. Version Roadmap

## v0.37 — Tool Execution Layer

目标：受权限和审计约束的工程工具执行基础。

包含：

- ToolExecutionPort
- EngineeringToolPort
- Permission
- Audit
- Adapters

禁止：

- Shell
- Flash
- Hardware Control

## v0.38 — Verification Agent

目标：验证 Agent 生成结果。

包括：

- Firmware Verification
- Hardware Constraint Check
- Build Verification

## v0.39 — Engineering Memory

目标：项目长期记忆。

包括：

- `board.yaml`
- `pin_map.json`
- `components.json`
- `decisions.md`
- `bugs.json`

## v0.40 — Component Intelligence

目标：器件级工程知识。

## v0.41 — PCB Intelligence

目标：PCB/EDA 数据解析。

支持：

- KiCad
- Altium
- 嘉立创 EDA

## v0.42 — Hardware Validation

目标：硬件约束验证。

## v0.43 — Flash Deployment

目标：受控烧录。

包括：

- J-Link
- ST-Link
- OpenOCD

需要：Human Approval。

## v0.44+ — Optimization Agent

目标：

```text
Telemetry
  ↓
Reasoning
  ↓
PID Optimization
```

# 7. Runtime Boundary

允许：

- Runtime 之间通过公开 Port 调用。

禁止：

- Runtime 直接访问其他 Runtime 内部实现。
- LLM 直接修改文件。
- LLM 直接执行命令。
- LLM 直接控制硬件。

# 8. Current Development Focus

当前：v0.37 Tool Execution Layer。

```text
ToolExecutionPort
  ↓
ToolRuntime
  ↓
EngineeringToolPort
  ↓
Adapter
  ↓
External Executor
```

Mock 只用于测试。生产环境通过 Adapter 注入具体 External Executor。

# 9. Future Expansion

未来支持：

- 真实编译
- CI 执行
- Flash
- 硬件调试
- PCB 分析
- 自动验证

所有扩展能力必须经过：

- Permission
- Verification
- Audit

# 10. Development Rules

Python：

- Python 3.11

测试要求：

- pytest
- ruff
- black
- compileall
- pip check

Git 规则：

- 使用版本化提交。
- 使用 tag 发布。
- 不污染历史 dirty 文件。
