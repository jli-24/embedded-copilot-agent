---
title: Engineering Memory
type: knowledge
status: implemented-development
layer: memory
version: v0.39
tags: [engineering-memory, provenance, verification]
aliases: [Engineering Memory, v0.39 Engineering Memory Layer]
---

# Engineering Memory

[[Engineering Memory]] 是工程事实、候选结论、验证证据与历史的可追溯记录边界。v0.39 已发布的实现是进程内、同步的参考 Store，不代表持久化知识库或 Agent 自动写入能力。

记录应区分 `CANDIDATE` 与 `VERIFIED`，保留来源、验证与人工批准关系。日常知识维护可从 [[工程日记模板]] 和 [[工程周记模板]] 开始；任何未验证的设计或故障结论必须明确标为候选。
