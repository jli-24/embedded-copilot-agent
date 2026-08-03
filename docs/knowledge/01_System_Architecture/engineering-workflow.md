---
title: Engineering Workflow
type: workflow
status: roadmap
layer: system
tags: [workflow, roadmap, verification]
aliases: [Engineering Workflow]
---

# Engineering Workflow

目标工程链路为：Requirement → Architecture → Hardware → PCB → Firmware → Build → Debug → Test → Optimization → [[docs/knowledge/99_Memory/engineering-memory|Engineering Memory]]。当前已发布版本只实现该链路中的部分 Runtime 基础，完整链路是路线图。

每一阶段应输出可审查的输入、假设、风险、证据和下一步；失败或超时必须进入显式恢复或 `WAIT_HUMAN`，不得伪装为成功。
