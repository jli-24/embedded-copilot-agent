---
title: Obsidian Vault 设计
type: knowledge-system
status: active
layer: documentation
tags: [obsidian, knowledge-management, architecture]
---

# Obsidian Vault 设计

本 Vault 将 [[docs/knowledge/00_Project_Overview/project-overview|Embedded Copilot Agent]] 的工程知识与路线图组织为可追溯页面。它是文档系统，不是运行时状态的来源。Vault 根目录应设为仓库根目录，因此 Dataview 路径从 `docs/knowledge` 开始。

## 目录职责

- `00_Project_Overview`：产品定位、范围和已知状态。
- `01_System_Architecture`：系统边界、数据流与工程工作流。
- `02_Agent_Design`：Agent 的职责、输入输出与状态边界。
- `03_Knowledge_System`：[[Knowledge Gateway]]、RAG、Datasheet 与工程记忆。
- `04_Engineering_Layers`：需求至测试的工程分层。
- `05_Version_History`：发布版本与未发布里程碑，严禁混写。
- `06_Decision_Log`：架构决策及其证据、状态和影响。
- `99_Memory`：日记、周记和 [[Engineering Memory]] 使用模板。
- `dashboard`：由 Dataview 聚合的只读导航页。

## 链接策略

使用带路径的 Obsidian wiki link 链接概念页，例如 [[docs/knowledge/02_Agent_Design/supervisor-agent|Supervisor Agent]]、[[docs/knowledge/03_Knowledge_System/rag|Knowledge Gateway]]、[[docs/knowledge/99_Memory/engineering-memory|Engineering Memory]]。跨层引用应优先链接概念，而不是复制内容。

## 标签与元数据

标签采用小写英文并按领域分组，例如 `#architecture`、`#agent`、`#rag`、`#roadmap`、`#implemented`。YAML 统一使用 `title`、`type`、`status`、`layer`、`version`（适用时）和 `tags`。`status` 只可表示事实状态：`released`、`implemented-development`、`design-milestone`、`roadmap` 或 `active`。

Dataview 页面只聚合这些 YAML 字段，避免从正文推断版本状态。
