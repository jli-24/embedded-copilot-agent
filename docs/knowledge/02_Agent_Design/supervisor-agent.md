---
title: Supervisor Agent
type: agent-design
status: roadmap
layer: orchestration
tags: [agent, supervisor, roadmap]
aliases: [Supervisor Agent]
---

# Supervisor Agent

Supervisor Agent 是目标多 Agent 架构的中央编排组件，负责调度、计划、状态管理和失败恢复，不承载领域推理或直接外部访问。

状态机：`PENDING`、`RUNNING`、`SUCCESS`、`FAILED`、`TIMEOUT`、`RECOVERY`、`WAIT_HUMAN`。它只能通过受控接口调用 [[docs/knowledge/03_Knowledge_System/rag|Knowledge Gateway]]、专业 Agent 和验证层。
