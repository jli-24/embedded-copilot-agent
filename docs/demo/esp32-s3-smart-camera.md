# ESP32-S3 Smart Camera Demo

## Scenario

输入需求：

> 设计一个低功耗 WiFi 摄像头。

本场景用于展示 Embedded Copilot v1.0 Engineering Core 与 Product Layer 的结构化数据流。
它是文档化、proposal-only 的演示，不读取真实项目文件，不调用设备、编译器或网络，也不声称
设计已经通过真实硬件验证。

## Engineering Flow

```text
Requirement
  -> Hardware Proposal
  -> Firmware Proposal
  -> Validation Plan
  -> Artifact
  -> Execution
  -> Optimization
  -> Release Report
```

### 1. Requirement

Requirement Intelligence 将用户需求投影为带 fingerprint 的
`EngineeringRequirementDocument`。安全摘要可表达低功耗、WiFi 与摄像功能目标；未提供的电源、
接口、电气和性能参数保持 unresolved，不通过关键词或模型推断补齐。

### 2. Hardware Proposal

Hardware Engineering 生成未验证的 `HardwareEngineeringProposal`，展示系统架构、显式器件候选、
接口合同、电源设计意图、BOM proposal、schematic intent 与 PCB constraint proposal。缺失的 pin、
voltage、clock、footprint、routing 和测量事实保持待审核状态。

### 3. Firmware Proposal

Firmware Engineering 基于 caller-owned platform projection 生成 BSP、Drivers、Middleware、
Application 和 Tests 的规划结构。该阶段不生成源码、文件路径、构建命令或可执行二进制。

### 4. Validation Plan

Hardware Validation 生成 deterministic `TestPlanProposal`，并将 caller-owned 或注入式 evidence
投影为安全分析。没有 VERIFIED evidence 时，相应结果保持 `UNKNOWN`；HIL 与 Digital Twin 也不被
描述为真实设备执行结果。

### 5. Artifact

Engineering Artifact Layer 将上游 proposal 聚合为 immutable artifact projections。`GENERATED`
只表示内存投影已形成，不表示 approved、verified、built 或 deployable。

### 6. Execution

Engineering Execution Layer 只有在 typed policy、approval 和显式 adapter binding 都有效时，才会
委托 caller-owned Port。此演示不注入真实 Build、Flash 或 Debug adapter，因此不会执行命令、访问
文件系统或控制硬件。

### 7. Optimization

Optimization Loop 只生成 deterministic mathematical candidate 和 reviewed projection。它不执行
真实调参、不采集测量、不修改 firmware，也不改变硬件状态。

### 8. Release Report

Product Layer 将各阶段的安全 reference、fingerprint、状态、时间线、review counts 与 decision
history 聚合为 `EngineeringReleaseReport`。报告不包含完整 requirement body、evidence body、
artifact content、执行日志或 Runtime object。

## Expected Product Projection

演示项目可表示为：

- Project：`ESP32-S3 Smart Camera`
- Session：单个 caller-owned `ProjectSession`
- Dashboard：Requirement 到 Optimization 的固定阶段状态
- Timeline：按固定阶段顺序排列的 reference-only events
- Decisions：包含 evidence/feedback reference 的可追踪决策投影
- Release Report：各阶段安全 reference 与 source fingerprint 的不可变汇总

所有 snapshot 均由调用方持有。Product Runtime 不保存 project registry、不维护全局 workspace
store、不自动持久化，也不隐式修改历史状态。
