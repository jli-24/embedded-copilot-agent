# Embedded Copilot Agent Engineering Guide

本文件是 Codex 和其他 AI Coding Agent 在本仓库中的工程开发规范。它定义当前开发边界、运行时 Agent 架构、代码与测试要求，以及长期 Roadmap。

除代码、变量名、类名、函数名、提交信息和技术关键词外，默认使用中文交流与编写项目文档。

## 1. Project Overview

### 1.1 项目定位

Embedded Copilot Agent 是一个面向嵌入式工程师的 AI Engineering Copilot。

项目不是通用聊天机器人，也不是完整的 EDA 自动设计系统。其核心价值是把以下能力组合成可追踪、可测试、可扩展的嵌入式研发工作流：

- LangGraph Multi-Agent Workflow
- RAG Knowledge Base
- Tool Calling
- FastAPI
- Embedded Engineering Tools

### 1.2 核心目标

项目长期辅助完成：

- Datasheet 知识检索
- MCU 与外设知识分析
- Firmware 开发辅助
- 编译错误与 Debug 日志分析
- PCB 设计分析
- 硬件方案与 BOM 辅助
- 电子设计竞赛方案分析
- 受控的 Computer Use 与构建调试闭环

长期目标不代表当前已经实现。任何能力只有在对应代码、测试和文档存在，并通过验证后，才能被描述为已实现。

### 1.3 当前开发边界

当前版本目标是 **v0.1 Foundation Agent System**，范围仅包括：

- Supervisor Agent
- Knowledge Agent
- Firmware Agent
- Debug Agent
- RAG
- Tool Calling
- FastAPI API
- Tests

v0.1 是当前实现范围，不等于所有条目已经完成。AI Coding Agent 必须根据仓库中的实际代码与测试判断完成状态，不得依据 Roadmap 推断功能已经可用。

以下能力不属于当前 v0.1 实现范围：

- Hardware Agent
- Competition Agent
- PCB Agent
- Multimodal Vision
- Computer Use Agent

除非用户单独批准对应版本的范围、接口、权限模型和测试计划，否则不得提前实现未来能力。

### 1.4 术语边界

本文中的 **Runtime Agent** 指项目运行时的 Supervisor Agent 和 Specialized Agents。本文中的 **AI Coding Agent** 指负责分析、修改和验证本仓库的 Codex 或其他开发助手。

“Runtime Agent 不得直接访问文件系统或执行 Shell”是产品架构约束，不禁止 AI Coding Agent 在获准的工程任务中使用开发工具修改本仓库。

## 2. System Architecture

### 2.1 当前 v0.1 架构

```text
User
  |
  v
API Layer
  |
  v
Supervisor Agent
  |
  +--> Knowledge Agent
  |
  +--> Firmware Agent
  |
  +--> Debug Agent
  |
  v
Tool Layer
  |
  v
Embedded Workspace
  |
  v
Output
```

### 2.2 数据流与职责

- API Layer：负责请求验证、依赖注入、调用应用服务，以及将内部结果映射为稳定的 API 响应。
- Supervisor Agent：负责意图识别、路由、Workflow 状态管理和结果整合。
- Specialized Agents：负责边界明确的领域推理，并返回结构化结果。
- Tool Layer：负责所有外部能力访问、输入验证、超时、错误封装和可审计执行。
- Embedded Workspace：代表受控的项目文件、知识文档、构建环境或设备资源。
- Output：必须通过结构化状态返回，失败不得伪装成成功。

RAG 属于知识检索能力，由明确接口提供给 Knowledge Agent；API、Agent、RAG 和 Tool 之间不得通过隐式全局状态耦合。

未来 Agent 不得加入当前架构图。它们只在第 5 节和第 10 节中定义。

## 3. Agent Rules

### 3.1 Supervisor Agent

Supervisor Agent 负责：

- 识别用户意图和任务类型
- 选择合适的 Specialized Agent
- 管理显式 Workflow State
- 控制路由、重试和终止条件
- 整合 Specialized Agent 与 Tool 的结构化结果

Supervisor Agent 禁止：

- 直接实现 Datasheet、Firmware 或 Debug 等领域业务逻辑
- 直接访问文件系统、网络、串口、编译器或其他外部资源
- 绕过 Tool Layer 调用外部能力
- 仅依赖自由文本 Prompt 隐式决定路由
- 创建无界循环或没有终止状态的 Workflow

### 3.2 Specialized Agent

每个 Specialized Agent 必须：

- 保持单一职责
- 使用有类型约束的结构化输入与输出
- 只读取任务所需的 Workflow State
- 通过结构化 State update 返回结果或错误
- 通过 Tool Layer 使用外部能力
- 保留必要的来源、Tool 调用和错误信息，支持追踪

Specialized Agent 禁止：

- 绕过 Tool Layer
- 直接修改其他 Agent 私有状态
- 隐式共享可变全局状态
- 扩展到未经批准的其他 Agent 职责
- 将不确定推断表达为已验证事实

### 3.3 LangGraph Workflow

每个 Workflow 必须：

- 定义显式、带类型约束的 State model
- 定义可检查、可测试的节点与条件边
- 定义结构化成功、失败和终止状态
- 为每个循环规定用途、最大迭代次数和终止条件
- 支持 State 检查，并为安全中断或恢复保留清晰边界
- 使 request、Agent selection、Tool call 和 result 之间可追踪

## 4. Current Agent Specification

本节只定义 v0.1 的三个 Specialized Agents。它不声明代码已经完成；实际状态以仓库实现和测试结果为准。

### 4.1 Knowledge Agent

职责：

- Datasheet 检索
- Embedded 文档检索
- 基于 RAG 的问答
- Source citation

Knowledge Agent 必须保留：

- 文档来源标识
- Source metadata，包括可用时的文件名、章节、页码或 URI
- 原始 Retrieval results 或其可追踪的结构化记录
- Retrieval result 与最终结论之间的引用关系

当检索结果为空、相关性不足、来源冲突或 metadata 缺失时，必须明确报告限制并建议下一步检索。禁止补造 Datasheet 参数、寄存器、引脚、单位、来源或引用。

### 4.2 Firmware Agent

知识范围：

- C/C++
- ESP-IDF
- STM32 HAL
- FreeRTOS

职责：

- 代码解释
- 代码生成
- 代码改进建议
- Firmware 与 RTOS 架构建议

输出必须明确关键假设，例如 MCU family、SDK/HAL version、clock、pin、peripheral、interrupt context 和 RTOS execution context。

除非存在真实硬件测量、构建或测试证据，否则禁止声称代码已经通过硬件验证。生成代码必须区分示例、可编译实现和已验证实现。

### 4.3 Debug Agent

职责：

- 编译错误分析
- ESP32 Guru Meditation 分析
- STM32 HardFault 分析
- Serial Log 分析

输出必须包含以下结构化字段：

- **Evidence**：日志、错误信息、寄存器值或调用栈中直接观察到的事实
- **Root Cause**：基于 Evidence 得出的原因；无法唯一确定时列出候选原因
- **Confidence**：对 Root Cause 可信程度的明确表达，并说明影响判断的缺失证据
- **Recommendation**：按优先级给出定位、修复和验证步骤

禁止在缺少证据时断言唯一 Root Cause。无法定位时必须说明还需要哪些日志、map file、ELF、register dump、源码位置或复现条件。

## 5. Future Agents Roadmap

本节只描述未来方向，不构成当前实现要求，也不表示兼容性已经存在。

### 5.1 Hardware Agent

未来职责：

- MCU 选型
- 外设选择
- 硬件方案比较
- BOM 生成

### 5.2 Competition Agent

未来职责：

- 全国大学生电子设计竞赛知识分析
- 蓝桥杯嵌入式赛题知识分析
- 历史题目检索
- 技术路线与方案分析

### 5.3 PCB Agent

目标处理链：

```text
EDA Parser
  |
  v
UnifiedPCBModel
  |
  v
Rule Engine
  |
  v
LLM Analysis
```

计划支持：

- KiCad
- EasyEDA
- Altium

PCB Agent 当前未在 v0.1 实现，目标版本为 v0.5 PCB Intelligence。列出某种 EDA 格式仅表示 Roadmap 方向，不得声称 Parser、UnifiedPCBModel、Rule Engine 或格式兼容性已经可用。

### 5.4 Multimodal Vision

未来能力：

- 图片输入
- Datasheet 或文档截图分析
- 原理图与 PCB 图片的辅助观察

Vision 输出必须区分 Observation、Inference 和 Recommendation。图片分析只能作为工程辅助，不能替代 EDA connectivity、DRC、ERC 或电气测量。

### 5.5 Computer Use Agent

未来能力：

- VS Code 操作
- Terminal 操作
- Build
- Debug

Computer Use 必须具备显式授权、资源边界、超时、取消、审计和失败恢复机制。未经单独批准，不得在当前版本添加可执行 Computer Use 能力。

## 6. Tool Layer Rules

Runtime Agent 的所有外部能力必须通过 Tool Layer 暴露。

Runtime Agent 禁止直接：

- 读取或修改文件
- 执行 Shell 命令
- 调用编译器、构建系统或 EDA 工具
- 访问串口、调试器、网络或外部服务

每个 Tool 必须：

- 定义明确的 input schema 和 output schema
- 在信任边界验证输入
- 返回结构化成功结果和结构化错误
- 显式处理 timeout、cancellation 和 permission
- 隐藏 provider、设备和环境实现细节
- 可独立注入、替换和测试
- 覆盖正常路径与异常路径测试

Tool 不得吞掉异常、返回含糊字符串代替错误类型，或记录 API Key、Token、密码、私有文档内容和敏感本地路径。

Tool 调用至少应产生可关联的结构化事件：

- `tool_called`
- `tool_completed`
- `error_occurred`

## 7. RAG Rules

知识库名称为 **Embedded Knowledge Base**。

### 7.1 当前知识范围

- ESP32
- STM32
- ARM Cortex
- FreeRTOS
- Communication Protocol，包括 UART、SPI、I2C、CAN、MQTT 和 TCP/IP
- Embedded Linux，包括 driver、BSP 和 Device Tree

### 7.2 Pipeline 要求

RAG pipeline 必须：

- 将文档解析为技术语义合理的 chunks
- 在 chunking 时保留代码、寄存器名、引脚名、单位和协议术语
- 生成并持久化 embeddings
- 在 ingestion、indexing、retrieval 和 citation 之间保留 metadata
- 返回可追踪的 Retrieval results 与 source citations
- 显式报告解析、索引和检索失败
- 支持可重复 ingestion，并避免重复数据静默污染索引
- 允许在测试中注入 embedding 和 retriever，默认不依赖在线服务

当前 vector store 使用 Chroma 即可。除非出现经过验证的需求并获得设计批准，不得引入 Neo4j、MinIO 或其他增加部署复杂度的组件。

生成的 vector store、未经授权的版权材料和机器相关索引不得提交到 Git。知识来源应保留已知的 source 与 license 信息。

## 8. Development Rules

### 8.1 技术栈

- Python 3.11
- FastAPI
- Pydantic
- LangGraph
- LangChain
- Chroma
- pytest

Provider、model、embedding、设备和环境配置必须放在配置层或窄接口 adapter 后，不得硬编码凭据、模型名、机器路径或硬件设置。

### 8.2 Project Skill Routing

Codex 中存在对应 Project Skill 时，按修改范围使用：

- `agent-architecture`：`agents/`、LangGraph Workflow、Supervisor routing 和 Tool Calling contract
- `rag-development`：`rag/`、文档 ingestion、chunking、embedding、retrieval 和 citation
- `python-backend`：`api/`、FastAPI、Pydantic、dependency injection、service 和 exception mapping
- `testing`：`tests/` 以及所有 Agent、Tool、RAG 或 API 行为变更
- `embedded-c-knowledge`：Firmware、MCU、peripheral、RTOS 和 embedded debug 相关事实
- `git-engineering`：branch、commit、tag、version、changelog 和 release

跨模块修改必须使用所有相关 Project Skills。Skill 用于约束开发过程，不得被 Runtime Agent 当作产品运行能力。

### 8.3 AI Coding Workflow

AI Coding Agent 执行开发任务时必须：

1. 先检查仓库结构、现有实现、测试和未提交修改。
2. 明确当前任务是否属于 v0.1；未来 Roadmap 能力必须先获得范围批准。
3. 大规模或跨模块修改前，先说明影响范围并提交设计与计划供用户批准。
4. 优先进行小而聚焦的修改，不修改无关代码。
5. 修改行为前先补充或调整测试，再实现最小满足需求的代码。
6. 遇到错误先稳定复现、读取完整错误并定位 Root Cause，不进行盲目修复。
7. 先运行 focused tests，再运行相关 regression suite。
8. 完成前进行 review，并报告验证证据、未验证部分和剩余限制。

### 8.4 代码规范

- Python 代码必须使用类型提示。
- 模块必须职责单一，避免在单文件堆积 Agent、Tool、RAG 和 API 逻辑。
- 公共接口和共享 schema 必须清晰、稳定并在边界验证输入。
- 保持 Agent 之间低耦合，通过显式 State、schema 或 service interface 通信。
- 异常必须显式处理，不得静默吞掉。
- 使用结构化日志，跨 API、Workflow、Agent、RAG 和 Tool 传播 trace identifier。
- 日志不得包含 Secret、Token、密码、私有文档正文或敏感本地路径。
- 外部依赖必须可注入，使测试默认不依赖真实硬件和在线服务。
- 不为未经批准的 Roadmap 添加推测性抽象或空壳实现。

### 8.5 接口与数据变更

修改以下内容前必须获得用户确认：

- 公共 API
- Workflow State 核心字段
- 共享 Pydantic model
- 持久化数据结构
- Tool 公共 schema

变更时必须说明兼容性影响、迁移方式和测试范围。

### 8.6 Git 规范

提交信息使用以下前缀：

- `feat:` 新功能
- `fix:` 问题修复
- `docs:` 文档或工程规范
- `test:` 测试

版本使用 Semantic Versioning，v0.x 阶段从 `v0.1.0` 开始。提交应保持聚焦，不得提交凭据、生成的 vector store、设备 dump 或机器相关文件。

## 9. Testing Rules

所有新增或修改的行为必须使用 pytest 覆盖：

- 正常路径
- 异常路径
- 输入验证与边界条件
- Workflow 路由、状态转换和终止条件
- Tool schema、错误映射、timeout 与 cancellation
- RAG parsing、chunking、retrieval、metadata 和 citation
- API validation 与 exception mapping

测试默认必须能在无真实硬件、无串口、无外部模型服务和无公网的环境中运行。使用 dependency injection、fake、stub、temporary directory 和临时 Chroma collection 隔离外部依赖。

禁止在新增行为没有测试的情况下声称任务完成。无法运行测试时，必须说明原因、未验证范围和可执行的后续验证命令。

完成前至少执行：

1. 与修改直接相关的 focused tests。
2. 受影响模块的 regression tests。
3. 条件允许时执行完整 offline test suite。

不得声称通过硬件验证，除非有明确的真实硬件测试证据。

## 10. Roadmap

Roadmap 只定义计划顺序。每个版本开始前必须分别批准 scope、architecture、permission model、test plan 和 completion criteria。

### v0.1 Foundation Agent

- Supervisor Agent
- Knowledge Agent
- Firmware Agent
- Debug Agent
- RAG
- Tools
- FastAPI API
- Tests

### v0.2 Multimodal

- 图片输入
- Datasheet 与文档截图分析
- Observation、Inference、Recommendation 结构化输出

### v0.3 Competition

- 电赛知识库
- 蓝桥杯知识库
- 历史题目检索
- 技术路线与方案分析

### v0.4 Hardware

- MCU 选型
- 外设选择
- 硬件方案比较
- BOM 生成

### v0.5 PCB Intelligence

- EDA Parser
- UnifiedPCBModel
- Rule Engine
- KiCad、EasyEDA 与 Altium 的分阶段支持
- 规则检查与 LLM 辅助分析

### v1.0 Engineering Copilot

- 整合成熟的 Agent、RAG 和 Embedded Engineering Tools
- 提供稳定、可观测、可审计的工程工作流
- 在独立安全设计获批后集成受控 Computer Use
- 形成从知识检索、开发辅助到构建与调试的工程闭环

Roadmap 版本中的条目在对应代码、测试和完成证据存在前，均视为未实现。

## 11. Repository Structure

目标目录结构：

```text
embedded-copilot-agent/
|-- AGENTS.md
|-- src/
|   `-- embedded_copilot/
|       |-- agents/
|       |-- rag/
|       |-- tools/
|       |-- api/
|       |-- schemas/
|       `-- services/
|-- tests/
|-- docs/
|-- knowledge/
|-- scripts/
|-- Dockerfile
|-- requirements.txt
`-- README.md
```

目录职责：

- `agents/`：只包含 Runtime Agent 行为、routing 和 Workflow node。
- `rag/`：负责 ingestion、parsing、chunking、embedding、indexing、retrieval 和 citation。
- `tools/`：只包含外部能力的结构化接口和实现。
- `api/`：只包含 FastAPI 路由、请求响应映射和 API 边界。
- `schemas/`：包含跨模块共享的 typed models 和 validation schemas。
- `services/`：包含不属于 Agent、Tool、RAG 或 API 的应用编排。
- `tests/`：镜像 `src/embedded_copilot/` 的相关模块结构。
- `docs/`：保存架构、决策、计划和操作文档。
- `knowledge/`：保存获准的知识来源或 import manifests，不保存生成的 vector store。
- `scripts/`：只保存小型、可重复的开发与维护命令，不承载生产业务逻辑。

禁止混合 Agent、Tool、RAG 和 API 的模块职责，也禁止把生产业务逻辑放入 `scripts/` 或测试文件。
