---
title: Debug Agent
type: agent-design
status: implemented-development
layer: debug
tags: [agent, debug, evidence]
aliases: [Debug Agent]
---

# Debug Agent

Debug Agent 的工程输出应包括 Evidence、Root Cause（或候选原因）、Confidence 和 Recommendation。当前 Runtime 基础以只读、确定性调试观察为原则；日志或寄存器不足时必须请求补充证据。
