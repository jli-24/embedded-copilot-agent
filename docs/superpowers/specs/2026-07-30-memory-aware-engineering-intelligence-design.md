# Embedded Copilot v0.40.0 Memory-aware Engineering Intelligence Layer Design

## 1. Summary

v0.40.0 将 v0.39.0 Engineering Memory 从被动保存工程经验的可信事实层，扩展为可被 Supervisor 和 Domain Agents 主动使用的工程认知来源。新增的 Memory Retrieval Layer 只读取既有 Memory public port，确定性筛选和排序 VERIFIED records，将结果投影为冻结的 `MemoryContext`，再与 Knowledge Gateway 结果组成强类型 `EngineeringPlanningContext`。

本版本是 read enhancement，不是 memory model rewrite。v0.40.0 不修改、替换或绕过 v0.39.0 的以下公共合同：

- `EngineeringMemoryStorePort`
- `EngineeringMemoryPort`
- `MemoryPermissionPort`、`MemoryAuthorizationRequest` 与 `MemoryPermissionDecision`
- `MemoryAuditSink` 与 `MemoryAuditEvent`
- `VerificationRequest`、`VerificationResult` 及 Verification Agent contracts

现有八方法 Store Port、单一 `EngineeringMemoryPort.execute()` 入口、Permission 最小披露、Audit 无内容事件、Verification binding、revision、receipt、immutable record 与 aggregate projection 均保持原义。v0.40.0 只新增 Retriever、Ranking、Memory Context 和 Supervisor read-side integration contracts。

Retriever 不写 Memory、不记录隐式 usage、不调用 LLM、不执行 Tool，也不访问 Store 内部容器。没有可用 Memory 或读取失败时，Supervisor 使用空 Memory context 继续既有 Agent workflow；Knowledge Gateway 与 Engineering Memory 保持独立来源，任何一方都不替代另一方。

## 2. Goals

- 为 Supervisor 提供稳定的 `Task Analysis -> Memory Retrieval -> Context Fusion -> Planning` 链路。
- 只把当前 Aggregate 中的 VERIFIED records 作为可信检索候选。
- 支持全部八类 Memory payload，并按 Domain、Verification evidence、historical usage 与 recency 确定性排序。
- 通过现有 `EngineeringMemoryPort` 完成读取，使 v0.39 Permission 和 Audit 边界继续生效。
- 通过 existing verified snapshot 与 revision-bound history 建立一致的 read-side evidence view。
- 输出冻结、strict、可确定性序列化并带 fingerprint 的 `MemoryContext`。
- 将 Memory 与 Knowledge 组合为强类型 `EngineeringPlanningContext`，同时保留二者独立 provenance。
- 在 Memory 未配置、为空或不可用时安全降级，不阻断 Domain Agents。
- 使每个排名因子、过滤原因、tie-break 和 context confidence 可测试、可解释。
- 保持 Workspace Runtime 为工程文件的唯一写边界。

## 3. Non-goals

v0.40.0 不包含：

- 修改 v0.39 Store、Memory、Permission、Audit 或 Verification public contracts。
- 新增 Memory mutation command、Store method、状态转换或 record replacement 规则。
- 读取 CANDIDATE、REJECTED、SUPERSEDED 或 REVOKED record 作为可信 Agent context。
- LLM 自主写入、自动批准、自动 Verification、自动状态修改、自动删除或覆盖历史。
- 因检索而更新 usage_count、record revision、aggregate revision 或 operation receipt。
- 向 v0.39 Record、Snapshot 或 Verification binding 增加字段。
- 向 Permission request、Audit event 或 Supervisor trace 写入 payload、Finding、Approval 正文或日志。
- Web Search、Browser Agent、网络爬虫、在线学习、embedding 或向量检索。
- 数据库、对象存储、真实持久化、cache、后台索引或跨进程同步。
- Workspace mutation、filesystem、Git、Shell、subprocess、构建、Flash、串口或硬件控制。
- API、UI、Streamlit 或 VS Code command integration。
- 根据自由文本相似度、LLM 判断或随机权重进行排序。

## 4. Current v0.39 Architecture

v0.39.0 使用不可变 Record、Aggregate projection 与由锁保护的 InMemory Store 临界区保存工程记忆：

```text
Trusted Caller
  |
  | EngineeringMemoryRequest
  v
EngineeringMemoryPort.execute()
  |
  +--> strict validation
  +--> MEMORY_REQUESTED audit
  +--> minimal permission authorization
  +--> eight-method EngineeringMemoryStorePort
  +--> terminal audit
  v
EngineeringMemoryResult
```

写操作由 operation receipt、request fingerprint、expected aggregate revision 与 record revision 保护。状态只允许通过 Verification、受限 Human Approval、replacement activation 或 explicit revoke 改变。Verification History 是 append-only identity，Workspace Runtime 继续是唯一文件写入口。

v0.39 的 verified snapshot 提供 `MemorySnapshotRecord` 的 payload、provenance、status、record revision 与 logical identity；history page 提供完整 immutable `EngineeringMemoryRecord`、state history、verification bindings、approval binding 与 transition timestamps。Retriever 利用这两个既有只读结果建立一致视图，不要求 v0.39 contract 添加 ranking 字段。

以下接口在 v0.40 中保持签名和职责不变：

```python
class EngineeringMemoryPort(Protocol):
    def execute(
        self,
        request: EngineeringMemoryRequest,
    ) -> EngineeringMemoryResult: ...


class EngineeringMemoryStorePort(Protocol):
    # Existing five mutation methods and three query methods remain unchanged.
    ...


class MemoryPermissionPort(Protocol):
    def authorize(
        self,
        request: MemoryAuthorizationRequest,
    ) -> MemoryPermissionDecision: ...


class MemoryAuditSink(Protocol):
    def record(self, event: MemoryAuditEvent) -> None: ...
```

## 5. v0.40 Architecture

目标链路为：

```text
User
  |
  v
Supervisor Agent
  |
  +--> Task Analysis
  |
  +--> EngineeringMemoryRetriever
  |      |
  |      +--> EngineeringMemoryPort: VERIFIED snapshot
  |      +--> EngineeringMemoryPort: revision-bound history pages
  |      +--> verified-only correlation
  |      +--> deterministic ranking
  |      `--> MemoryContext
  |
  +--> Knowledge Gateway --> KnowledgeContext
  |
  +--> EngineeringPlanningContext
  |
  +--> Planning and domain-specific context projection
  v
Domain Agents
  |
  v
Verification Agent
  |
  v
Engineering Memory write workflow owned by trusted caller
```

Retrieval 与 Memory mutation 是不同能力。Retriever 只能构造 `GetVerifiedSnapshotRequest` 和 `GetHistoryRequest`，不得构造或 dispatch 任何写命令。Verification Agent 的结果仍需由受信调用方通过原有 Memory write workflow 提交；Supervisor 不能把自己的输出直接写入 Memory。

新增模块职责固定为：

```text
src/embedded_copilot/engineering_memory/
  retrieval.py   # Retriever composition, input isolation and consistent reads
  ranking.py     # Pure domain mapping, factor normalization and ordering
  context.py     # Read-side strict DTOs and deterministic context fingerprint
```

现有 `ports.py`、Store Port、service、audit、permission、rules 和 Verification package 不因 Retrieval 改写。未来实现可以在 `engineering_memory.__init__` 中追加批准的 read-side exports，但不得删除或改变 v0.39 exports。

## 6. Memory Retrieval Model

公开入口固定为：

```python
def create_engineering_memory_retriever(
    *,
    memory_port: EngineeringMemoryPort,
) -> EngineeringMemoryRetriever: ...


class EngineeringMemoryRetriever:
    def retrieve(
        self,
        request: MemoryRetrievalRequest,
    ) -> MemoryContext: ...
```

工厂拒绝缺失 `execute()`、异步方法或不满足 runtime-checkable `EngineeringMemoryPort` 的依赖。Retriever facade 只公开同步 `retrieve()`，不公开底层 port、ranking helper、history iterator 或容器。

`MemoryDomain` 固定为 `FIRMWARE`、`HARDWARE`、`PCB`、`DEBUG` 与 `GENERAL`。

`MemoryUsageSignal` 字段固定为：

- `record_id`
- `usage_count`：strict non-negative integer，排名时按 20 封顶

`MemoryRetrievalBinding` 是 Supervisor task 的可选冻结绑定，字段固定为：

- `request_id`
- `project_id`
- `memory_id`
- `caller`
- `requested_at`：UTC-aware
- `usage_signals`：按 `record_id` 唯一并稳定排序的 tuple
- `limit`：默认 8，范围 1–50

`MemoryRetrievalRequest` 复用 binding 字段，并增加由 Task Analysis 生成的非空、唯一、稳定排序 `domains`。调用方不能提供 candidate inclusion、raw Store filter、ranking weight、permission decision 或 snapshot。

Retriever 执行固定流程：

1. deep-copy 并重新验证 request。
2. 为底层只读命令生成确定性 child request ID：对 canonical retrieval request、阶段名和页码执行 SHA-256，使用 `mr-` 加前 32 位小写十六进制。
3. 通过 `EngineeringMemoryPort.execute()` 获取 VERIFIED snapshot。
4. 通过同一 port 分页读取 history；首个 history page 与 snapshot aggregate revision 必须相同，后续页使用 v0.39 revision-bound cursor。
5. 只关联 verified snapshot 中列出的 record IDs；每个 snapshot record 必须存在唯一 history record，且 payload、provenance、status、revision、logical key 与 memory type 一致。
6. 要求关联的 full record 仍为 VERIFIED，最终 transition 与 Verification/Human Approval binding 一致。
7. 要求所有 usage signal 的 record ID 存在于 verified snapshot；未知或重复 ID 拒绝请求。
8. 执行 domain filtering、ranking、limit、context construction 和输出重验证。

任何 snapshot/history aggregate revision 不一致、cursor conflict、缺失或重复 record、状态不一致、未来 transition timestamp 或输入被依赖修改，都使整次检索 fail closed。Retriever 不返回部分 `MemoryContext`。

空 Aggregate 或没有 domain-compatible record 时返回合法的空 `MemoryContext`，不视为异常。

## 7. Ranking Model

排名只消费关联后的 immutable VERIFIED records 和 caller-owned usage signals。所有因子先转换为 `0..1000` 整数，再计算总分；不使用随机数、模型、embedding 或运行期可变权重。

### Verification confidence

v0.40 不向现有 Verification binding 增加原始 confidence 字段。该因子表示当前 v0.39 evidence path 的确定性完整度：

- 最终 transition 为 `VERIFICATION`，且最后一个关联 binding 为 `PASS`：1000。
- 最终 transition 为 `HUMAN_APPROVAL`：0；该记录仍可检索，但不得伪装为经过技术 Verification。
- 其他 binding/state 组合：拒绝整个 context。

该值不是故障概率，也不把 `FAIL` 提升为已确认硬件故障。Retriever 只读取已经为 VERIFIED 的记录，因此 FAIL、REVIEW_REQUIRED 或 candidate evidence 不参与排名。

### Domain relevance

- record domain 与任一请求 domain 精确匹配：1000。
- record 只映射到 `GENERAL`：500。
- 无匹配：从候选集过滤。

Domain 映射固定为：

- Board Profile、Component、Pin Binding、Interface Binding、Power Constraint：`HARDWARE` 与 `PCB`。
- Verification History：`FIRMWARE` subject 映射 `FIRMWARE`；`HARDWARE` 映射 `HARDWARE` 与 `PCB`；`TOOL_RESULT` 映射 `GENERAL`。
- Engineering Decision 与 Known Issue：优先使用最终 PASS binding subject；没有 PASS binding 时，`CODING_RESULT` 映射 `FIRMWARE`，`DEBUG_SNAPSHOT` 或 `TELEMETRY_RESULT` 映射 `DEBUG`，`DATASHEET_RESULT` 映射 `HARDWARE` 与 `PCB`，其余 provenance 映射 `GENERAL`。

### Historical usage

`usage_millis=min(usage_count, 20) * 50`。没有 signal 的 record 为 0。Usage 只影响本次排序，不写回 Retriever、Memory、Supervisor 或 Audit；同一 request 和同一 snapshot 始终产生相同结果。

### Recency

以 caller-provided `requested_at` 减去 record `last_transition_at`：

- 不超过 30 天：1000
- 大于 30 天且不超过 180 天：750
- 大于 180 天且不超过 365 天：500
- 大于 365 天：250

`last_transition_at` 晚于 `requested_at` 表示绑定时间不一致，整次 context 被拒绝。Runtime 不读取系统时钟。

### Total and ordering

```text
total_millis = (
    4 * verification_millis
    + 3 * domain_millis
    + 2 * usage_millis
    + recency_millis
) // 10
```

公开 `relevance_score` 为 `total_millis / 1000`，使用三位小数的确定性表示。排序 key 固定为：

```text
-total_millis
-verification_millis
-domain_millis
-usage_millis
-recency_millis
memory_type.value
logical_key
record_id
```

`MemoryRankingBreakdown` 保存五个整数因子、`total_millis` 与公开 score。调用方不能改变权重或 tie-break。

## 8. Memory Context Contract

所有 read-side DTO 继承同一 strict frozen base：

```python
ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    revalidate_instances="always",
    strict=True,
)
```

`MemoryTrustBasis` 固定为 `VERIFICATION` 与 `HUMAN_APPROVAL`。

`MemoryContextEvidence` 字段固定为：

- `record_id`
- `memory_type`
- `logical_key`
- `trust_basis`
- `verification_subject: VerificationSubjectType | None`
- `verification_confidence: float | None`：read-side 投影值；PASS path 为 1.0，Human Approval 为 `None`
- `provenance_source_type`
- `provenance_reference`
- `last_transition_at`
- `ranking: MemoryRankingBreakdown`

Evidence 不包含 Finding、Approval evidence、完整 state history、源码、日志、路径、secret 或异常文本。

`MemoryContext` 字段固定为：

- `request_id`
- `project_id`
- `memory_id`
- `aggregate_revision`
- `domains`
- `records: tuple[MemorySnapshotRecord, ...]`
- `evidence: tuple[MemoryContextEvidence, ...]`
- `confidence`
- `source_snapshot_fingerprint`
- `context_fingerprint`

records 与 evidence 必须长度一致、按排名顺序一一对应，并具有唯一 record ID。Context 不超过 request limit。空 context 的两个 tuple 为空、confidence 为 0.0，仍绑定 aggregate revision 与 source snapshot fingerprint。

`MemoryContext.confidence` 表示所选上下文的 evidence completeness，不是工程事实永真概率：

- Verification-backed record 使用 1.0。
- Human Approval-only record 使用 0.5，表示工程接受但未经过技术 Verification。
- 非空 context 取所有 selected record evidence confidence 的最小值。
- 空 context 为 0.0。

`context_fingerprint` 使用重新验证后的 JSON、UTF-8、稳定字段顺序、紧凑分隔符、`allow_nan=False` 和 SHA-256；计算输入排除 `context_fingerprint` 本身，包含 request binding、aggregate revision、domains、records、evidence、confidence 与 source snapshot fingerprint。

## 9. Supervisor Integration

Supervisor 的同步公开 `run(task)` 入口保持不变。未来实现对 `AgentTask` 与 `AnalysisCommand` 增加可选的 `memory_binding: MemoryRetrievalBinding | None`；默认 `None` 保持现有调用兼容。

执行顺序固定为：

```text
AgentTask
  -> requirement analysis and agent/domain selection
  -> optional MemoryRetrievalRequest construction
  -> Memory Retrieval or safe fallback
  -> optional Knowledge Gateway retrieval
  -> EngineeringPlanningContext fusion
  -> deterministic planning
  -> domain-specific context projection
  -> Agent dispatch
```

`EngineeringPlanningContext` 是冻结 strict DTO，包含：

- revalidated `SupervisorTask`
- `knowledge_context: KnowledgeContext | None`
- `memory_context: MemoryContext | None`
- `selected_domains`
- `fusion_fingerprint`

没有 binding 时 `memory_context=None`，Supervisor 不调用 Retriever。绑定存在但没有匹配 records 时保留合法的 empty `MemoryContext`，使 planning 可以区分“已查询但为空”和“未配置”。

Planner 使用 record types、IDs、logical keys、ranking evidence 和安全 payload projection 生成 Agent invocations。Dispatcher 为每个 Domain Agent 重新过滤 context，只传递与该 Agent domain 相符或 GENERAL 的 records，并 deep-copy/revalidate metadata。Agent 不能获得 Retriever、MemoryPort、permission、audit 或 Store 对象。

Supervisor trace 增加 `memory_retrieved`、`memory_fallback` 与 `context_fused` stages。Trace 只保存 status、target、domains 和 count，不保存 Memory payload、record content、Permission reason、Audit event、异常文本或本地路径。

## 10. Knowledge Gateway Fusion

Knowledge Gateway 与 Engineering Memory 的职责固定为：

| Source | Provides | Trust interpretation |
|---|---|---|
| Knowledge Gateway | Datasheet、manual、specification、approved external knowledge | 可引用的外部知识，不表示项目已采用 |
| Engineering Memory | Project facts、verified solutions、engineering decisions、known issues、verification history | 项目内已通过 v0.39 trust transition 的记录 |

`EngineeringPlanningContext` 保留两个独立字段、独立 fingerprints 与独立 provenance。Fusion 不进行去重覆盖，不允许 Memory 替换 Datasheet specification，也不允许 RAG result 覆盖 verified project decision。

冲突处理固定为：

- 两个来源均保留，并以来源类型标记。
- Planner 在 rationale 中标记需要 Verification 或工程师复核的冲突。
- Fusion 不写 Memory、不自动选择胜者、不生成 replacement candidate。
- Knowledge 为空时 Memory 可继续使用；Memory 为空或 fallback 时 Knowledge 与 Agent workflow 继续。

`fusion_fingerprint` 对 revalidated Supervisor task identity、KnowledgeContext fingerprint/projection、MemoryContext fingerprint/projection 与 selected domains 进行 canonical SHA-256。它用于确定性与测试，不作为写操作 authorization 或 receipt。

## 11. Security Boundary

Memory Retrieval package 必须满足：

- 只依赖 public `EngineeringMemoryPort` 和公开 frozen DTO；不导入 Store adapter、Aggregate、lock、service 或内部容器。
- 只构造 `GetVerifiedSnapshotRequest` 与 `GetHistoryRequest`；静态测试禁止引用五类 mutation request。
- 不调用 Verification Agent，不修改 Verification Result，不把 Human Approval 表达为技术 Verification。
- 不读取 CANDIDATE 或其他非 VERIFIED 状态作为可信 context。
- 不读取系统时钟、环境变量、filesystem、database、network，不生成 UUID 或随机值。
- 不调用 Agent、Model、LLM、RAG、Tool、Workspace、Git、Shell、subprocess 或 hardware。
- 不维护模块级 mutable usage state、cache、background task、async worker 或 learning loop。
- 不提供 delete、update、save、approve、verify、replace 或 mutation callback。
- 不把 payload、Finding、Approval、日志、路径、secret 或 exception 原文写入 audit、trace 或 error。
- 对被篡改输入、依赖修改 request、畸形 snapshot/history、非法状态与 revision mismatch fail closed。

Security AST tests 固定新增模块集合与 import/call/token allowlist，同时回归 v0.39 Store Port 八方法、MemoryPort 单一 `execute()`、Permission 九字段最小披露、Audit event schema 与 Verification public contract 未变化。

## 12. Permission Boundary

Retriever 不新增 Permission Port，也不接收 caller-provided permission decision。每个底层 snapshot/history 查询都通过既有 `EngineeringMemoryPort.execute()`，因此继续执行 v0.39 固定链：strict validation、requested audit、minimal permission authorization、Store query、terminal audit、result。

Retriever 传递的底层 query 只包含现有字段：child request ID、project ID、memory ID、caller、requested_at，以及 history cursor/limit。Domains、usage signals、ranking weights、Agent task、Knowledge results 和 MemoryContext 不进入 `MemoryAuthorizationRequest`。

Permission deny 由现有 MemoryPort 抛出 `MemoryPermissionDenied`。Retriever 不绕过、不重试为未经授权的 Store read，也不降级为 candidate query。Supervisor 捕获清洗异常后使用空 context 继续，不向 Agent 或 trace 暴露 permission metadata。

## 13. Audit Boundary

Retriever 不新增 Audit contract 或 Audit sink。既有 `MEMORY_REQUESTED` 与 terminal event 为每个 deterministic child query 提供审计，事件 key 和 UTC timestamp 继续使用 v0.39 规则。

Snapshot 与每个 history page 使用不同、确定性的 child request ID，避免同一 audit event key 对应不同 query metadata。相同 retrieval request replay 生成相同 child IDs；Audit sink 的逻辑幂等语义不变。

Audit event 不增加 domains、ranking、usage、record IDs、payload、evidence、context fingerprint 或 fallback 原因。Supervisor trace 不是 Memory security audit，也不能替代 MemoryAuditSink。

Audit requested 或 terminal event 失败时，现有 MemoryPort 不交付对应 query result。Retriever 不使用部分页面构造 context；Supervisor 按 Failure Matrix 降级且不泄露已读取内容。

## 14. Failure Handling

Retriever 公开清洗后的 `MemoryRetrievalError`、`MemoryRetrievalRequestRejected` 与 `MemoryRetrievalUnavailable`。异常不包含 payload、record content、底层 exception、adapter type、路径、日志、Permission/Audit 内容或 traceback。

Memory Retrieval Failure Matrix 固定为：

| Situation | Retrieval behavior | Supervisor behavior |
|---|---|---|
| 无 Memory binding 或无匹配 Memory | 不读取或返回合法 empty context | 继续 Agent workflow |
| Permission 拒绝 | 不绕过、不返回 snapshot | 使用空 Context，继续 Agent |
| Snapshot/history 异常或 revision 不一致 | fail closed，不返回部分结果 | 使用空 Context，并记录安全 fallback trace |
| CANDIDATE、非法状态或 trust binding 不一致 | 拒绝整个上下文 | 使用空 Context，继续 Agent |
| Audit 失败 | 不交付对应读取内容 | 使用空 Context，不泄露内容 |
| Retriever 异常或畸形输出 | 抛出清洗后的 unavailable | fallback，继续 Agent |

Request 自身字段不合法时 Retriever 抛出 `MemoryRetrievalRequestRejected`；在直接调用 Retriever 的边界上不伪装为成功。Supervisor 作为 optional enrichment consumer 捕获该异常并 fallback，保证 Memory integration 不成为 Agent 可用性的单点阻断。

Fallback 后 `EngineeringPlanningContext.memory_context=None`，trace stage 为 `memory_fallback`、status 为 `error`、count 为 0。不得把异常类型、permission reason 或已读取 record count 写入下游 Agent metadata。

## 15. Testing Strategy

未来实现按 TDD 覆盖：

- Factory 依赖检查、同步 `retrieve()` 窄接口和严格 exports。
- DTO frozen、strict、extra forbid、UTC-aware、tuple 唯一排序、篡改嵌套实例重验证。
- v0.39 `EngineeringMemoryStorePort` 仍为八方法，`EngineeringMemoryPort` 仍只有 `execute()`。
- Permission、Audit 与 Verification contracts 的字段、签名和 export compatibility。
- Retriever 只发出 verified snapshot/history queries，绝不构造 mutation command。
- VERIFIED filtering 与全部非 VERIFIED 状态拒绝。
- Snapshot/history identity、payload、revision、aggregate revision 和 binding correlation。
- 多页 history cursor、并发 revision drift、缺页、重复 record 与部分结果拒绝。
- 全部八种 payload 的 Domain 映射与 GENERAL fallback。
- Verification/Human Approval trust basis 与 confidence semantics。
- verification、domain、usage、recency 的 0/边界/封顶测试。
- 30/180/365 天 recency 边界和 future timestamp 拒绝。
- 40/30/20/10 integer scoring、三位小数 projection 与完整 tie-break 顺序。
- usage signal 重复、未知 record、bool-as-int、输入 mutation 与无内部 usage state。
- limit 1/8/50、空 context、stable ordering 与 repeated-request determinism。
- `MemoryContext` records/evidence 对齐、immutability、canonical serialization 和 fingerprint tamper detection。
- Knowledge-only、Memory-only、combined 与 both-empty `EngineeringPlanningContext`。
- Supervisor memory injection、per-domain projection、未配置与空 Memory fallback。
- Failure Matrix 六类行为，确保 Agent 继续且 trace 无内容。
- Permission deny、Audit fail、Store unavailable、Retriever malformed result 不泄露内容。
- Security AST gate：无 Store internals、mutation、LLM/RAG call、filesystem/network/database/Shell/Git/hardware。
- v0.39 Engineering Memory、Verification Agent、Workspace、Tool 和 Supervisor regression。

测试默认使用 fake `EngineeringMemoryPort` 与既有 InMemory reference composition，不使用真实数据库、网络、文件、硬件或在线模型。并发一致性测试使用明确同步原语，不使用 timing sleep。

## 16. Release Strategy

本设计提交只新增：

```text
docs/superpowers/specs/2026-07-30-memory-aware-engineering-intelligence-design.md
```

设计提交信息固定为 `docs: add v0.40 memory intelligence design`。它不修改 `src/`、`tests/`、README、architecture、PROJECT_CONTEXT、package version、Settings、HealthResponse 或 release metadata，不创建 tag，不 push，也不生成 implementation plan。

设计提交从 `main/origin/main=e6ddd9684884821cbd4f7d91bc5d9402c723fa25` 的独立 worktree 分支创建。原 main checkout 中 README、Demo、Web、release metadata、`.agents`、`.claude` 与历史 release dirty 必须保持原样；目标 commit parent 必须为该固定 HEAD，commit tree 相对 parent 只新增目标文档。

未来 v0.40 implementation plan 必须单独批准，并明确生产文件、测试文件、Public Contract compatibility、focused/security/regression gates、版本同步、staged-tree validation、功能提交与 annotated `v0.40.0` tag。只有实现、测试、质量门禁、cached diff 和 staged tree 全部通过后才能创建 release commit/tag；本设计不执行这些未来动作。

v0.40 发布文档必须将能力描述为 deterministic read-side Memory retrieval 和 memory-aware planning，不得声称实现持久化、在线学习、自动写 Memory、自动修复、硬件验证或执行闭环。
