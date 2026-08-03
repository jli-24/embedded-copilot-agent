---
title: Architecture Decisions
type: decision-log
status: active
layer: architecture
tags: [adr, architecture, security]
aliases: [Architecture Decisions]
---

# Architecture Decisions

## ADR-001：Runtime 与 Agent 分离

状态：已采用。Runtime 通过公开 Port 与冻结 DTO 提供确定性能力；Agent 编排属于更高层目标架构，不能越过外部访问边界。

## ADR-002：验证和记忆分离候选与事实

状态：已采用。[[Verification Agent]] 的规则结果与 [[Engineering Memory]] 的 `CANDIDATE` / `VERIFIED` 状态防止未经验证的结论成为工程事实。

## ADR-003：执行能力必须受控

状态：已采用原则，执行扩展为路线图。文件写入、构建、烧录或硬件控制必须由权限、审计、超时、取消和人工批准共同约束。

## ADR-004：最终愿景不等于当前实现

状态：已采用。[[System Architecture]] 用状态字段区分 released、implemented-development、design-milestone 与 roadmap。
