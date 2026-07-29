# Embedded Copilot v0.39.0 Engineering Memory Layer Design

## 1. Summary

v0.39.0 新增独立、framework-independent 的 Engineering Memory Layer，为 Embedded Copilot 提供可验证、可追踪且确定性的工程记忆基础。它保存调用方明确提交的工程事实候选、决策、已知问题与验证历史，并通过 Verification 或受限的 Human Approval 将候选推进到可信状态。

本层采用不可变 Memory Record、Aggregate projection 和原子领域命令 Store。它不进行推理，不调用 Agent 或 LLM，不执行工具，不读写工程文件，也不把 Memory 变成另一个执行边界。Workspace Runtime 继续是工程文件的唯一写边界。

v0.39.0 首版只提供同步、进程内、线程安全的参考实现。所有标识、时间、审批和验证证据均由调用方提供；Runtime 不读取系统时钟，不生成 UUID 或随机值。公共 DTO 采用 Pydantic strict contract：`frozen=True`、`extra="forbid"`、`revalidate_instances="always"`、严格类型、UTC-aware 时间和确定性序列化。

## 2. Goals

- 提供独立于 Agent framework、API framework、数据库和 UI 的 Engineering Memory contract。
- 用不可变记录保存 Board、Component、Pin、Interface、Power、Decision、Known Issue 和 Verification History。
- 严格区分 `CANDIDATE` 与 `VERIFIED`，禁止把未验证推断表达为工程事实。
- 支持 Verification Result 驱动的确定性状态转换，并保存不可变绑定。
- 只允许 Engineering Decision 与 Known Issue 使用明确的 Human Approval。
- 用 Aggregate revision 提供 optimistic concurrency control。
- 用 `operation_id`、请求 fingerprint 和 operation receipt 提供写操作幂等。
- 用最小披露的 Permission contract 和无工程内容的 Audit event 建立安全边界。
- 提供线程安全的 InMemory Store，作为 contract、状态机和并发语义的参考适配器。
- 提供稳定的 verified/candidate snapshot 与 revision-bound history pagination。
- 为未来 JSON、SQLite、Redis 等 Store adapter 提供稳定公共合同，但本版不实现这些 adapter。

## 3. Explicit Non-goals

v0.39.0 不包含：

- 数据库、对象存储、向量数据库或任何真实持久化适配器。
- Agent、Model、LLM、RAG、embedding、prompt 或自主记忆生成。
- Verification Agent 调用；Memory 只消费调用方提供的冻结 Verification Request 与 Result。
- Workspace、filesystem、Shell、subprocess、Git、网络、硬件、串口、调试器或构建控制。
- API、CLI、UI、Streamlit、VS Code 命令或后台任务。
- 自动修复、自动执行、自动审批、默认放行或策略学习。
- RBAC、JWT、用户数据库、签名系统或审批服务。
- UUID、随机数、系统时间或环境变量读取。
- hard delete、可变记录、原地覆盖或普通 CRUD 接口。
- 多租户、跨项目共享记忆、TTL、归档、压缩或保留期策略。
- 完整 Event Sourcing、跨进程锁、分布式事务或持久化迁移。

## 4. Architecture

```text
Trusted Caller
  |
  | EngineeringMemoryRequest
  v
EngineeringMemory Facade
  |
  v
EngineeringMemoryPort.execute()
  |
  +--> strict revalidation + canonical fingerprint
  +--> MemoryAuditSink: MEMORY_REQUESTED
  +--> MemoryPermissionPort: minimal authorization request
  +--> EngineeringMemoryStorePort: atomic command or query
  +--> MemoryAuditSink: terminal event
  |
  v
EngineeringMemoryResult
```

核心实现采用三层模型：

1. **Immutable Record**：保存 payload、provenance、状态、revision、verification/approval binding 和 state history；任何变化都产生新 Record 值。
2. **Aggregate projection**：以 `(project_id, memory_id)` 为边界维护 aggregate revision、records、逻辑槽位投影与 operation receipts；Aggregate 是 Store 内部状态，不是公共 DTO。
3. **Atomic domain-command Store**：在同一临界区内完成 receipt 检查、revision 检查、状态转换、双记录替代、projection 更新与 receipt 保存。

拒绝完整 Event Sourcing：首版不需要事件重放、事件版本迁移、持久化日志或跨服务订阅，完整事件系统会扩大依赖与恢复语义。拒绝细粒度 CRUD：分别暴露 record update、projection update 和 receipt write 会破坏替代、revision 与幂等的原子性。状态历史和 audit 是不可变追踪信息，但不构成 Event Sourcing 数据库。

## 5. Public Facade and Ports

公开工厂与 facade 固定为：

```python
def create_engineering_memory(
    *,
    store: EngineeringMemoryStorePort,
    permission_port: MemoryPermissionPort,
    audit_sink: MemoryAuditSink,
) -> EngineeringMemory: ...


class EngineeringMemory:
    def memory_port(self) -> EngineeringMemoryPort: ...


class EngineeringMemoryPort(Protocol):
    def execute(
        self,
        request: EngineeringMemoryRequest,
    ) -> EngineeringMemoryResult: ...


class MemoryPermissionPort(Protocol):
    def authorize(
        self,
        request: MemoryAuthorizationRequest,
    ) -> MemoryPermissionDecision: ...


class MemoryAuditSink(Protocol):
    def record(self, event: MemoryAuditEvent) -> None: ...
```

`EngineeringMemory` 只公开 `memory_port()`；业务调用只有同步 `execute()`。Facade 不公开 service、rules、fingerprint、audit helper、Aggregate、lock、Store 内部容器或 InMemory 实现细节。

工厂对三个依赖执行 runtime-checkable Protocol 校验，拒绝缺失方法、异步方法和非法实现。依赖由受信 composition root 注入；调用方不能在单次请求中替换 permission、audit 或 store。

计划模块布局：

```text
src/embedded_copilot/engineering_memory/
  __init__.py
  facade.py
  factory.py
  ports.py
  models.py
  service.py
  rules.py
  fingerprint.py
  audit.py
  exceptions.py
  stores/
    __init__.py
    in_memory.py
```

模块职责固定为：`__init__.py` 只导出批准的公共合同；`facade.py` 提供窄 facade；`factory.py` 验证依赖并完成装配；`ports.py` 定义同步 Protocol；`models.py` 定义 frozen strict DTO；`service.py` 编排 validation、audit、permission 与 Store；`rules.py` 保存纯确定性状态和兼容规则；`fingerprint.py` 只负责 canonical serialization 与 SHA-256；`audit.py` 构造无内容事件和稳定 event key；`exceptions.py` 定义清洗异常；`stores/in_memory.py` 提供私有线程安全 reference adapter。

## 6. Aggregate and Revision Model

一个 Aggregate 由 `(project_id, memory_id)` 唯一标识。其内部包含：

- `aggregate_revision`：不存在 Aggregate 的逻辑 revision 为 `0`；每个成功 mutation 恰好增加 `1`。
- `records`：按 `record_id` 保存不可变 `EngineeringMemoryRecord`。
- `active_verified_by_logical_key`：普通逻辑槽位当前生效的 verified record 投影。
- `candidate_by_logical_key`：仍在验证或审批中的 candidate 投影。
- `operation_receipts`：按 `operation_id` 保存 fingerprint 与无工程内容的原始 mutation result。
- `verification_request_ids`：记录 Aggregate 内已创建的 Verification History identity。

所有写命令携带 `expected_revision`。Store 的固定检查顺序是：

1. 查找 `operation_id` receipt。
2. receipt 存在且 fingerprint 一致时，返回原始 result，不检查当前 revision，不重复 mutation。
3. receipt 存在但 fingerprint 不一致时，抛出 `MemoryOperationConflict`。
4. receipt 不存在时比较 `expected_revision` 与当前 aggregate revision。
5. revision 不一致时抛出 `MemoryRevisionConflict`。
6. 在单一原子 mutation 中执行状态、projection、revision 和 receipt 更新。

因此已经成功的操作可用旧 `expected_revision` 安全重放；新的操作不能绕过 optimistic concurrency control。

## 7. Immutable Memory Record

`EngineeringMemoryRecord` 至少包含：

- `project_id`
- `memory_id`
- `record_id`
- `memory_type`
- `logical_key`
- 强类型 `payload`
- `provenance`
- `status`
- `record_revision`
- `created_aggregate_revision`
- `last_updated_aggregate_revision`
- `created_at`
- `last_transition_at`
- tuple 形式的 `verification_bindings`
- 可选 `approval_binding`
- tuple 形式的 `state_history`
- 可选 `supersedes_record_id`
- 可选 `superseded_by_record_id`

新记录固定为：

- `record_revision=0`
- `status=CANDIDATE`
- 初始 history 为 `from_status=None`、`to_status=CANDIDATE`

调用方不得直接提供 `status`、`logical_key`、`record_revision`、`state_history`、verification binding 或 approval binding；这些字段只能由 Runtime 的确定性规则生成。

初始创建是 Aggregate mutation，因此 aggregate revision 增加 `1`；记录的 `created_aggregate_revision` 与 `last_updated_aggregate_revision` 均绑定该 mutation 的新 revision。后续每一次成功状态转换都令 `record_revision+1`，并更新 `last_updated_aggregate_revision`。Record 和其嵌套 DTO 均不可变；Store 通过构造新值替换内部引用，不修改已交付对象。

## 8. Strongly Typed Payloads

`MemoryPayload` 是带 `memory_type` discriminator 的封闭 union，只允许以下 DTO：

- `BoardProfileMemory`：`board_id`、`board_name`、`mcu_family`、`mcu_model`、`architecture`。
- `ComponentMemory`：`component_reference`、`component_type`、`part_number`、`manufacturer`、`quantity`。
- `PinBindingMemory`：`target_id`、`pin_id`、`function`、`component_reference`、`interface_reference`。
- `InterfaceBindingMemory`：`target_id`、`interface_id`、`signal`、`pin_id`、`component_reference`。
- `PowerConstraintMemory`：`supply_id`、`load_id`、`minimum_voltage_mv`、`maximum_voltage_mv`、可选 `maximum_current_ma`。
- `EngineeringDecisionMemory`：`decision_topic`、`decision`、`rationale_summary`。
- `KnownIssueMemory`：`issue_key`、`title`、`severity`、`description_summary`、`mitigation_summary`。
- `VerificationHistoryMemory`：`verification_request_id`、`subject_type`、`verification_status`、稳定排序的 `finding_categories` 和 `confidence_basis`。

字符串必须非空并经过规范化；标识采用受限字符集；tuple 输入必须拒绝重复项并稳定排序；数值必须有明确单位和合法范围。电压与电流使用整数单位，Power 范围要求 `minimum_voltage_mv <= maximum_voltage_mv`。不接受自由形状 dict、任意 JSON payload、可变 list/set 或未经声明的扩展字段。Verification History 只保存安全摘要和引用，不复制源码、日志、完整 Finding 或原始硬件数据。

Payload 可以包含工程内容，因此只进入 Record、Store 和授权前 fingerprint 计算；不得进入 Permission request、Audit event、operation receipt 或异常文本。

## 9. Trust State Model

状态枚举固定为：

- `CANDIDATE`：已记录但尚未通过允许的验证或审批路径。
- `VERIFIED`：已通过兼容的 Verification，或属于允许人工审批的类型且获得有效批准。
- `REJECTED`：兼容的 Verification 返回 `FAIL`。
- `SUPERSEDED`：曾生效的 verified record 已被同逻辑槽位的新 verified record 原子替代。
- `REVOKED`：调用方明确撤销 candidate 或 verified record；不删除历史。

允许的转换为：

```text
None       -> CANDIDATE
CANDIDATE  -> VERIFIED
CANDIDATE  -> REJECTED
CANDIDATE  -> CANDIDATE   (Verification REVIEW_REQUIRED)
VERIFIED   -> SUPERSEDED  (replacement activation only)
CANDIDATE  -> REVOKED
VERIFIED   -> REVOKED
```

其余转换全部以 `MemoryStateTransitionRejected` 拒绝。`REJECTED`、`SUPERSEDED` 与 `REVOKED` 是终态，恢复信息必须创建新 Record。调用方不能直接创建 `VERIFIED` 或设置 `SUPERSEDED`。`FAIL` 表示当前候选没有通过 Verification 规则，不等于已确认真实硬件故障、设备损坏或根因；Memory 只保存 Verification 给出的候选语义，不提升其事实等级。`VERIFIED` 表示满足本系统的可信转换条件，不表示绝对事实永远正确。

`REVIEW_REQUIRED` 不创建新状态。它保存 Verification binding，追加 `CANDIDATE -> CANDIDATE` history，令 record revision 增加 `1`、aggregate revision 增加 `1`，并保存 operation receipt。

## 10. Provenance

每个 Record 必须携带冻结的 `MemoryProvenance`：

- `source_type`
- `source_reference`
- `source_revision`
- `created_by`
- `observed_at`：UTC-aware 时间

`source_type` 固定为 `USER_INPUT`、`DATASHEET_RESULT`、`CODING_RESULT`、`DEBUG_SNAPSHOT`、`TELEMETRY_RESULT`、`TOOL_RESULT`、`VERIFICATION_RESULT` 或 `MANUAL_DECISION`。

Provenance 描述信息从何而来，不表示信息已经验证。`source_type=VERIFICATION_RESULT` 也不能单独把 Record 提升为 `VERIFIED`；状态转换必须经过正式 Verification binding 规则。

Provenance 创建后不可修改，replacement record 必须提供自己的 provenance。`source_reference` 只能是安全引用 ID，禁止路径、源码、文件内容、日志全文、二进制或 secret。Runtime 不打开 provenance reference，不读取路径或 URI，不联网校验来源，也不生成时间或 ID。

## 11. Logical Key

每种 payload 使用确定性 logical key：

- Board Profile：`board-profile`
- Component：`component:<component_reference>`
- Pin Binding：`pin:<target_id>:<pin_id>`
- Interface Binding：`interface:<target_id>:<interface_id>:<signal>`
- Power Constraint：`power:<supply_id>:<load_id>`
- Engineering Decision：`decision:<decision_topic>`
- Known Issue：`issue:<issue_key>`
- Verification History：`verification:<verification_request_id>`

所有片段先按各 DTO 的标识规则规范化，再拼接；Runtime 根据 payload 计算 key，不允许调用方提供 logical key，也不使用 LLM、文本相似度或模糊匹配。普通逻辑槽位在任一时刻最多有一个 active verified record 和一个显式 replacement candidate；普通创建不能占用已有可信槽位。

Verification History logical key 是 append-only identity，不属于普通逻辑槽位，不出现在 replacement projection 中。即使对应记录后来 `REJECTED` 或 `REVOKED`，同一 Aggregate 内也不能再次创建相同 `verification_request_id`。重复 verification logical key、对其创建 replacement 或应用 Human Approval 均以清洗后的 `MemoryStateTransitionRejected` 拒绝。

## 12. Replacement Semantics

替代只能通过 `CreateReplacementCandidateRequest` 发起。命令必须指定当前 active verified `supersedes_record_id`，新 payload 必须产生与旧记录相同的普通 logical key，且新 `record_id` 未使用。

创建 replacement 时：

- 新记录以 `CANDIDATE`、`record_revision=0` 创建。
- 旧记录继续保持 `VERIFIED` 并继续出现在 verified snapshot。
- candidate snapshot 显示新记录及 `supersedes_record_id`。

新候选获得 `PASS` 或允许的有效 Human Approval 时，Store 在一次 Aggregate mutation 中：

1. 将旧记录 `VERIFIED -> SUPERSEDED`，旧记录 revision 增加 `1`。
2. 将新记录 `CANDIDATE -> VERIFIED`，新记录 revision 增加 `1`。
3. 互相写入 supersession binding。
4. 原子切换 active verified projection。
5. aggregate revision 只增加 `1`。
6. 保存一个 operation receipt。

新候选 `REVIEW_REQUIRED` 或 `REVOKED` 时旧记录继续生效；新候选 `FAIL` 时新记录进入 `REJECTED`，旧记录不变。任一步验证失败、revision 冲突或 Store 异常都不得交付半完成替代。已经 `SUPERSEDED` 的旧记录不会自动恢复。

## 13. Verification Binding

`ApplyVerificationRequest` 同时携带调用方提供的冻结 v0.38 `VerificationRequest` 与 `VerificationResult`。Memory 不调用 Verification Agent；它重新验证嵌套实例，要求：

- request 与 result 的 `request_id` 完全一致。
- command、Record、Verification request 的 project/context binding 一致。
- result 是对应 request 的完整最终结果，不接受单个 checker 的部分结果。
- Record 当前为 `CANDIDATE`，且 `record_revision` 与命令一致。
- 同一 verification request 不能以不同内容绑定到同一 Record。

确定性 context id 固定为 `memory:<project_id>:<memory_id>:<record_id>:<record_revision>`，Verification request 必须与该值精确绑定。

Payload 与 Verification subject 的兼容表固定为：

| Memory payload | 允许的 Verification subject |
|---|---|
| Board Profile | `HARDWARE` |
| Component | `HARDWARE` |
| Pin Binding | `HARDWARE` |
| Interface Binding | `HARDWARE` |
| Power Constraint | `HARDWARE` |
| Engineering Decision | `FIRMWARE`、`HARDWARE`、`TOOL_RESULT` |
| Known Issue | `FIRMWARE`、`HARDWARE`、`TOOL_RESULT` |
| Verification History | 必须与 payload 自身 `subject_type` 精确一致 |

状态映射固定为：

- `PASS`：`CANDIDATE -> VERIFIED`；replacement 使用第 12 章的双记录原子转换。
- `FAIL`：`CANDIDATE -> REJECTED`。
- `REVIEW_REQUIRED`：`CANDIDATE -> CANDIDATE`，保存 binding 并增加 record 与 aggregate revision。

Verification binding 保存 request id、subject type、result status、request/result fingerprint、requested_at 和确定性 summary reference。完整 Finding 只能存在于获准的 Record payload/binding 数据中，不进入 permission、audit、receipt 或异常。

## 14. Human Approval

Human Approval 只允许作用于 `EngineeringDecisionMemory` 与 `KnownIssueMemory`。Board、Component、Pin、Interface、Power 和 Verification History 必须通过 Verification 路径，不能用人工审批绕过技术验证。

`HumanApprovalEvidence` 是冻结 strict DTO，固定包含：

- `approval_id`
- `record_id`
- `record_revision`
- `approved_by`
- 受限 `reason_code`
- `approved_at`：UTC-aware 时间

`ApplyHumanApprovalRequest` 必须重新验证 evidence，并精确匹配当前 Record ID 与 revision。有效 approval 令普通 candidate 进入 `VERIFIED`，replacement candidate 使用双记录原子转换。`approval_id` 在 Aggregate 内不可重复使用；approval 不能更新终态记录、不能用于 Verification History，也不能包含自动修复、执行动作或 patch。人工批准表示项目接受该记录，不表示技术事实已经被客观证明。

## 15. State History

`MemoryStateTransition` 是 Record 内 append-only tuple 项，包含：

- `from_status: MemoryStatus | None`
- `to_status: MemoryStatus`
- `request_id`
- `operation_id`
- `evidence_type`
- `evidence_reference`
- `reason_code`
- `transitioned_at`：复用命令的 UTC-aware `requested_at`

新记录初始 transition 为 `None -> CANDIDATE`，其 `record_revision=0`。后续每追加一个 transition，Record 的 `record_revision` 必须严格增加 `1`。`REVIEW_REQUIRED` 明确追加一项 `CANDIDATE -> CANDIDATE`，不压缩、不覆盖旧历史。

State history 不保存 payload、Finding、Approval 正文、源码、日志、路径或异常文本。Record 的 verification/approval binding 保存必要的结构化证据；history 只描述状态变化。

## 16. Public Commands

`EngineeringMemoryRequest` 是按 `command_type` 判别的封闭 union。公共请求类型固定为：

- `CreateCandidateRequest`
- `CreateReplacementCandidateRequest`
- `ApplyVerificationRequest`
- `ApplyHumanApprovalRequest`
- `RevokeRecordRequest`
- `GetVerifiedSnapshotRequest`
- `GetCandidateSnapshotRequest`
- `GetHistoryRequest`

所有请求共享：

- `request_id`
- `project_id`
- `memory_id`
- `caller`
- UTC-aware `requested_at`

写命令额外统一包含 `operation_id` 与 `expected_revision`：

- `CreateCandidateRequest`：`record_id`、强类型 `payload`、`provenance`。
- `CreateReplacementCandidateRequest`：`record_id`、强类型 `payload`、`provenance`、`supersedes_record_id`。
- `ApplyVerificationRequest`：`record_id`、`record_revision`、`verification_request`、`verification_result`。
- `ApplyHumanApprovalRequest`：`record_id`、`record_revision`、`approval`。
- `RevokeRecordRequest`：`record_id`、`record_revision`、受限 `reason_code`。

只读命令不包含 `operation_id` 或 `expected_revision`：

- `GetVerifiedSnapshotRequest`
- `GetCandidateSnapshotRequest`
- `GetHistoryRequest`：可选 `cursor` 与 `limit=50`，其中 limit 范围为 `1..100`。

`command_type`、payload discriminator 与实际 DTO 类型必须一致。任何额外字段、bool 代替 int、naive datetime、非法 enum、空标识、重复 tuple 项或被构造后篡改的嵌套实例都在进入 audit 前以 `EngineeringMemoryRequestRejected` 拒绝。

## 17. Idempotency

Service 对重新验证后的完整请求执行 canonical serialization：

1. Pydantic `mode="json"` 输出。
2. `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`。
3. UTF-8 编码。
4. SHA-256 小写十六进制摘要。

写操作以 `(project_id, memory_id, operation_id)` 为幂等域。Receipt 保存：

- `operation_id`
- `request_fingerprint`
- `command_type`
- 无工程内容的 `MemoryMutationResult`
- mutation 后的 aggregate revision

相同 operation 与相同 fingerprint 返回原始 result；相同 operation 与不同 fingerprint 抛出 `MemoryOperationConflict`。Receipt 检查先于 revision 检查，保证成功操作的 stale retry 不重复 mutation。

`request_id` 标识一次逻辑调用，调用方不得把同一 request id 用于不同请求。查询不写 operation receipt，但 permission binding 与 audit key 均绑定 query fingerprint 或 request identity。Audit sink 对相同 key、不同安全元数据的事件必须 fail closed，不能静默合并。

## 18. Permission

`MemoryPermissionPort` 不接收完整 `EngineeringMemoryRequest`。Service 在 strict revalidation 与完整请求 fingerprint 完成后，只构造独立冻结的 `MemoryAuthorizationRequest`：

```python
class MemoryAuthorizationRequest(StrictFrozenModel):
    request_id: str
    operation_id: str | None
    project_id: str
    memory_id: str
    caller: str
    command_type: MemoryCommandType
    action: MemoryAction
    request_fingerprint: str
    requested_at: AwareDatetime
```

该 DTO 不包含 Memory Payload、Verification Finding、完整 Verification Request/Result、Approval 内容、源码、日志、路径或 provenance 内容。查询的 `operation_id=None`；写操作必须为非空 operation id。`action` 是由 Runtime 根据 command type 推导的受限枚举，不能由调用方自行提升。

`MemoryAction` 固定为 `READ_VERIFIED_MEMORY`、`READ_CANDIDATE_MEMORY`、`READ_MEMORY_HISTORY`、`CREATE_MEMORY_CANDIDATE`、`APPLY_VERIFICATION_EVIDENCE`、`APPLY_HUMAN_APPROVAL`、`CREATE_REPLACEMENT_CANDIDATE` 或 `REVOKE_MEMORY_RECORD`。

`MemoryPermissionDecision` 必须回显 request 中的全部绑定字段，并包含明确的 `ALLOWED` 或 `DENIED` 与 allowlisted `reason_code`。Service 对返回实例重新验证并逐字段精确比较；字段缺失、额外字段、绑定不符、异常或畸形返回都 fail closed。调用方不能在业务 request 中提供 permission decision，也不存在默认允许路径。

Permission deny 记录 `MEMORY_REJECTED` 并抛出 `MemoryPermissionDenied`；permission adapter 异常或非法 decision 记录 `MEMORY_FAILED`，并以清洗后的 `MemoryPermissionDenied` fail closed。Permission 不读取或解释工程 payload。

## 19. Audit

事件类型固定为：

- `MEMORY_REQUESTED`
- `MEMORY_COMPLETED`
- `MEMORY_REJECTED`
- `MEMORY_FAILED`

`MemoryAuditEvent` 是冻结、无工程内容 DTO，只保存 `event_key`、event type、request id、可选 operation id、project id、memory id、可选 record id、command type 与 `timestamp`；其中 `timestamp` 精确复用 request 的 UTC-aware `requested_at`。它不保存 Payload、源码、路径、日志、Finding、Approval、异常原文、traceback 或 Store 内容。

稳定逻辑幂等键固定为：

- 写操作：`memory-audit:<request_id>:<operation_id>:<event_type>`
- 查询：`memory-audit:<request_id>:<event_type>`

Audit sink 必须以 `event_key` 去重。相同 key 与完全相同安全元数据重复提交只形成一个逻辑事件；相同 key 携带不同元数据时必须拒绝。所有事件复用请求中的 UTC-aware `requested_at`，Runtime 不读取当前时间。

执行顺序固定为：

```text
strict validation
  -> MEMORY_REQUESTED audit
  -> permission
  -> receipt/revision/state checks
  -> Store mutation or query
  -> terminal audit
  -> result
```

显式请求、权限、revision、operation 或 state conflict 记录 `MEMORY_REJECTED`。Store、permission 或内部不可用记录 `MEMORY_FAILED`。`MEMORY_REQUESTED` 写入失败时不调用 Permission 或 Store，并抛出 `MemoryAuditUnavailable`。

Mutation 已成功而 terminal audit 失败时不回滚 Store、不交付 result，并抛出 `MemoryAuditUnavailable`。同一 operation replay 先命中 receipt，不重复 Store mutation，再以相同 terminal `event_key` 重试 audit；即使前一次 sink 在持久化事件后才报错，也不得形成重复逻辑事件。查询 terminal audit 失败时同样不返回 snapshot/history，但查询本身不产生 mutation。

## 20. InMemory Store

`InMemoryEngineeringMemoryStore` 是 v0.39.0 唯一参考适配器。它满足 `EngineeringMemoryStorePort`，但不从 package facade 导出实现类。特性固定为：

- 进程内、非持久化、同步。
- 每个 Store 实例拥有私有容器和 `threading.RLock`。
- 不使用模块级可变状态。
- 不使用 `sleep` 解决并发。
- 每个 domain command 在单个锁保护的临界区内完成全部读取、校验、copy-on-write、projection 更新和 receipt 保存。
- 先预计算新 Aggregate 值，所有规则通过后一次替换内部引用。
- 返回冻结副本，不泄露内部 dict、list、lock 或 Aggregate。
- 不提供 delete、clear、truncate 或 bypass 方法。

Store 的 mutation port 接收 Runtime 内部的已授权 domain command 和已计算 fingerprint。它原子处理：

- operation receipt 命中与冲突。
- expected aggregate revision。
- record revision 与状态。
- logical key uniqueness。
- Verification History identity uniqueness。
- replacement 的双记录转换。
- verified/candidate projection。
- aggregate revision 与 receipt。

Store 不执行 permission 或 audit，不计算授权，不读取时钟，不访问 filesystem。未来持久化适配器必须保持相同原子 contract；不能把这些步骤拆成公开 CRUD 调用。

## 21. Query Model

`GetVerifiedSnapshotRequest` 返回当前 active verified projection；`GetCandidateSnapshotRequest` 返回当前 candidate projection，包括等待复核的 replacement candidate。`EngineeringMemorySnapshot` 绑定 `project_id`、`memory_id`、`aggregate_revision`、`board_profile`、`components`、`pin_bindings`、`interface_bindings`、`power_constraints`、`engineering_decisions`、`known_issues`、`verification_records` 和 snapshot fingerprint。`board_profile` 最多一条，各集合为 frozen tuple，并按 `(logical_key, record_id)` 稳定排序。快照返回安全 provenance reference、record ID、revision 与 status，不泄露 Store 内部对象。

`GetHistoryRequest` 返回 `EngineeringMemoryHistoryPage`，包含冻结的 `records`、`aggregate_revision`、可选 `next_cursor` 与 `has_more`。每条 Record 携带完整的 append-only `state_history`。Record 排序固定为：

1. Record 的 `created_aggregate_revision`。
2. `record_id`。

Record 内 transition 保持原追加顺序。History 不支持模糊、全文或向量检索。

Cursor 语法固定为：

```text
revision:<aggregate_revision>:offset:<n>
```

首次查询不带 cursor，Store 在锁内绑定当前 aggregate revision，从 offset `0` 读取，并在还有后续项时返回包含该 revision 的 next cursor。后续页必须携带首次查询的 aggregate revision。若当前 aggregate revision 与 cursor revision 不同，Store 以 `MemoryRevisionConflict` 拒绝，Service 记录 `MEMORY_REJECTED`；调用方必须从无 cursor 查询重新开始。这样避免并发 mutation 导致跨页重复或遗漏。

Cursor 必须严格匹配语法，revision 与 offset 为非负十进制整数，不能包含空格、符号、前后缀或额外段。非法 cursor 属于 `EngineeringMemoryRequestRejected`。`limit` 默认 `50`，只允许 `1..100`。

## 22. Public Results and Exceptions

`EngineeringMemoryResult` 是封闭 union：

- `MemoryMutationResult`：request id、operation id、command type、outcome、受影响 record ids 与 revisions、aggregate revision；不含 payload。
- `EngineeringMemorySnapshot`：request id、snapshot type、aggregate revision、分类的冻结 records tuple 与 fingerprint。
- `EngineeringMemoryHistoryPage`：request id、bound aggregate revision、冻结 records tuple、可选 next cursor 与 has more。

公共异常均为清洗后的稳定类型：

- `EngineeringMemoryError`
- `EngineeringMemoryRequestRejected`
- `MemoryPermissionDenied`
- `MemoryAuditUnavailable`
- `MemoryStoreUnavailable`
- `MemoryRevisionConflict`
- `MemoryOperationConflict`
- `MemoryStateTransitionRejected`
- `MemoryRecordNotFound`

异常消息只包含安全 reason code 与必要标识，不包含 payload、Finding、Approval、源码、日志、路径、内部异常、adapter 类型或 traceback。底层异常使用 exception chaining 保留给受信调用栈，但不进入公开 DTO 或 audit event。

## 23. Security Boundary

Engineering Memory package 的静态与运行时边界固定为：

- 不导入或调用 Agent、Model/LLM、RAG、API、Streamlit、Tool、Workspace、VS Code、Git、网络、hardware、Shell 或 subprocess。
- 不调用 Verification Agent；只重新验证并消费公开冻结 Verification contracts。
- 不读取 filesystem、环境变量、系统时间，不生成 UUID 或随机数。
- 不暴露 Aggregate、内部 Store command、rules、fingerprint helper、audit helper、lock 或内部容器。
- 不提供 async、background task、callback 执行、dynamic import、reflection dispatch 或 eval/exec。
- 不提供 hard delete、raw update、raw dict payload、自动审批、自动修复或执行动作。
- 不接受 caller-supplied `VERIFIED`、caller-supplied `SUPERSEDED` 或默认成功 Verification。
- Permission 只看最小授权 DTO；Audit 只看无内容事件。
- Workspace Runtime 保持工程文件的唯一写边界；Memory Store mutation 只改变 Memory 自身的进程内结构化状态。

静态安全测试将固定 package 文件集合，检查 AST import、call 与 token，禁止上述依赖和能力；同时回归 Reasoning、Coding、Workspace、VS Code、Debug、Telemetry、Tool 与 Verification 的现有 facade 和只读/写边界。

## 24. Testing Strategy

未来实现必须按 TDD 先写失败测试，再实现最小行为。测试至少覆盖：

- 工厂依赖、Protocol 校验、facade 窄接口与严格 exports。
- DTO freeze、extra forbid、strict 类型、UTC-aware、tuple 去重排序和嵌套篡改重验证。
- canonical JSON 与 SHA-256 稳定性、Unicode、字段顺序和非法数值。
- 八类 payload、logical key、provenance 与 Verification subject 兼容表。
- 新记录 `record_revision=0` 与 `None -> CANDIDATE` history。
- PASS、FAIL、REVIEW_REQUIRED，其中 self-transition 同时增加 record/aggregate revision 并保存 receipt。
- Human Approval 仅允许 Decision/Issue，且完整 binding 必须匹配。
- replacement 延迟生效、PASS/有效人工批准双记录原子转换、失败无半状态。
- Verification History append-only、重复 identity、replacement 与 approval 拒绝。
- operation receipt 先于 revision、相同 replay、fingerprint conflict 与并发重复提交。
- Permission 最小披露、decision echo、deny、异常、畸形输出与 fail closed。
- Audit requested/completed/rejected/failed、稳定 event key、sink 去重、requested 失败前置阻断、terminal 失败后的 mutation replay。
- verified/candidate snapshot、稳定排序、fingerprint 与不可变结果。
- history cursor grammar、revision binding、并发 revision 变化、分页无重复遗漏和 limit 边界。
- InMemory Store thread safety、不同 Aggregate 隔离、copy-on-write 与无内部对象泄漏。
- 公共异常清洗和无工程内容 audit/receipt。
- 安全 AST 门禁与现有 Runtime boundary regression。

计划测试文件为：

```text
tests/engineering_memory/
  test_contracts.py
  test_mutations.py
  test_state_transitions.py
  test_queries.py
  test_idempotency.py
  test_in_memory_store.py
tests/security/test_engineering_memory_boundary.py
tests/release/test_v039_release.py
```

这些文件属于未来实现阶段，本设计提交不创建或修改测试。并发测试使用同步原语建立确定性交错，不用 `sleep`；还要明确验证无重复 VERIFIED logical slot、无部分 replacement、facade compatibility 与现有 Runtime regression。

## 25. Release and Quality Gate

未来 v0.39.0 实现完成时，需将版本同步为 `0.39.0`，更新 `pyproject.toml`、package version、`Settings.version`、`HealthResponse.version`、compatibility assertions、README、`docs/architecture.md`、`docs/PROJECT_CONTEXT.md` 与 `docs/release/v0.39.0.md`，并保留旧 release tests 的历史断言。继续使用 Python 3.11 和现有环境，不安装新依赖。发布过程采用 staged-tree validation、staged Python Black manifest、Black 26.5.1、Ruff、pytest、compileall、pip check、cached diff check 与 `git write-tree`。发布前至少依次执行：

```powershell
pytest tests/engineering_memory -q
pytest tests/security/test_engineering_memory_boundary.py -q
pytest tests/release/test_v039_release.py tests/release/test_contract_compatibility.py tests/release/test_release_metadata.py -q
pytest -q
ruff check .
black --check .
python -m compileall -q src tests
python -m pip check
git diff --check
```

任何 focused、security、release、regression 或 quality gate 失败都不得创建 v0.39.0 release commit/tag。未来发布是否采用增量 formatting gate 必须由当次批准的 release plan 明确；本设计不改变当前 181 个历史 Black formatting 差异。

本次任务只提交设计文档，不同步版本、不实现 package、不创建 release note 或 tag。

未来实现通过全部门禁且 staged tree 准确后，发布提交计划为 `feat: add engineering memory layer`，annotated tag 为 `v0.39.0`，不 push。该未来发布动作不属于本设计文档提交。

## 26. Git Isolation

本设计提交的执行基线固定为：

- branch：`main`
- `HEAD` 与 `origin/main`：`bec1d71ca863d984f584304894a378052d2fbf23`
- annotated tag `v0.38.0` 的目标：`b9498ea68867a169065a14bc5eb9f300ea1c7269`
- Git index：空

必须保留以下历史 dirty，不 reset、restore、checkout、stash、clean、覆盖或暂存：

- `README.md`
- `demo/esp32_camera/manifest.json`
- `tests/release/test_release_metadata.py`
- `tests/web/`
- `web/`
- `.agents/skills/developing-with-streamlit`
- `.claude/`
- `docs/release/v0.20.1.md`

只允许新增并暂存 `docs/superpowers/specs/2026-07-29-engineering-memory-design.md`，使用精确路径 `git add`，禁止 `git add .`。提交前必须验证 cached name 只有该文件，审查完整 cached diff，运行 `git diff --cached --check` 并成功 `git write-tree`。

提交信息固定为 `docs: add v0.39 engineering memory design`，commit parent 必须是上述 `HEAD`。本任务不创建 tag、不 push、不生成 implementation plan，也不修改 `src/`、`tests/`、version metadata 或其他文档。

## 27. Open Questions

本设计的实现决策已经全部关闭：

- 采用不可变 Record、Aggregate projection 与原子领域命令 Store。
- 新记录 revision、状态和初始 history 语义固定。
- `REVIEW_REQUIRED` 使用有 revision 的 `CANDIDATE -> CANDIDATE` 转换。
- Verification subject/payload 兼容表固定。
- Verification History 使用 append-only identity，不参与普通替代或 Human Approval。
- Permission 使用独立、冻结且最小披露的 authorization DTO。
- 写操作幂等先检查 receipt，再检查 aggregate revision。
- History pagination 使用 revision-bound cursor。
- Audit 使用稳定 event key，并对 mutation 后审计重试去重。
- v0.39.0 首版只提供同步、线程安全的 InMemory Store。

后续实现必须遵守本文 contract；任何改变公共 DTO、状态机、Store 原子边界、权限披露、Audit 幂等或 cursor 语义的方案，都需要新的明确设计批准。
