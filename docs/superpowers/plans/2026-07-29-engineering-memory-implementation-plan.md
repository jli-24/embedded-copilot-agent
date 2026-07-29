# Embedded Copilot v0.39.0 Engineering Memory Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a framework-independent, contract-first Engineering Memory Layer with immutable typed records, deterministic trust transitions, optimistic concurrency, idempotent mutations, permission binding, fail-closed audit, typed snapshots, paged history, and a thread-safe in-memory reference store.

**Architecture:** EngineeringMemoryPort exposes one synchronous execute() entry. EngineeringMemoryService validates frozen commands, audits requests, obtains a fingerprint-bound permission decision, and delegates atomic domain commands to EngineeringMemoryStorePort. v0.39 provides only InMemoryEngineeringMemoryStore and does not perform filesystem, database, network, Tool, Agent, LLM, Workspace, or hardware operations.

**Tech Stack:** Python 3.11, Pydantic, typing.Protocol, threading synchronization, pytest, Ruff, Black 26.5.1, Git staged-tree validation.

## Global Constraints

- Python 必须为 3.11.x；实施开始时动态寻找现有且可运行的解释器，不把机器路径写入项目。
- 不安装、升级、修复或修改依赖；环境检查失败时在 Task 1 前停止。
- Ruff 只要求 `python -m ruff --version` 和后续 CLI gate 可执行，不要求 `import ruff`。
- 所有公共 DTO 使用 `frozen=True`、`extra="forbid"`、`revalidate_instances="always"` 和 strict validation。
- 所有时间必须 timezone-aware，并规范化为 UTC；Runtime 不读取系统时钟。
- Runtime 不生成 UUID 或随机 ID。
- Runtime 不访问 filesystem、database、network 或 environment。
- Runtime 不调用 Agent、Supervisor、Model、LLM、RAG、Tool、Workspace mutation 或 hardware。
- Workspace Runtime 仍为唯一工程文件写边界。
- 不允许 hard delete、默认授权或默认 Verification 成功。
- 不允许调用方直接创建 `VERIFIED` 或 `SUPERSEDED`。
- 不允许失败后交付部分结果。
- v0.39 只实现同步、线程安全、进程内的 `InMemoryEngineeringMemoryStore`；不存在任何数据库事务机制。
- receipt 检查、revision 检查、状态转换、双记录替代、projection 更新和 receipt 写入必须在同一个由锁保护的 Store 临界区完成。
- 全仓 181 个历史 Black 差异不在本版本处理；Black 只检查最终 staged tree 自动生成的 Python manifest。
- 历史 dirty 文件不得意外进入 index；重叠文件只允许基于执行前 HEAD 构造 index-only 更新。
- 各 Task 只运行 focused tests、diff review 和 staged-tree checkpoint，不创建中间实现提交。
- 最终发布只创建一个 `feat: add engineering memory layer` 功能提交和一个 annotated `v0.39.0` tag；不 push。
- 任一 RED/GREEN、security、release、regression、quality、cached diff 或 tree equality gate 失败时，不 commit、不 tag、不声明完成。

## Execution Preflight

在 Task 1 前记录 branch、HEAD、parent、origin/main、tag、index 和历史 dirty。动态枚举已有 Python 命令或虚拟环境解释器；对选中的解释器依次运行等价于以下命令的检查：

```powershell
python --version
python -c "import pytest, pydantic, embedded_copilot; print('imports OK')"
python -m black --version
python -m ruff --version
python -m pip check
```

通过条件是 Python 为 `3.11.x`、Black 精确为 `26.5.1`、Ruff CLI 可执行、pytest/Pydantic/package 可导入且 `pip check` 成功。不得通过安装或改变依赖修复 preflight；任一条件不满足时保持代码、测试、版本和 index 不变并停止。

## File Responsibility Map

### Production files

- `src/embedded_copilot/engineering_memory/models.py`：按依赖顺序定义枚举、严格基础模型、payload、provenance、record/evidence、commands、permission/audit 和 results。
- `src/embedded_copilot/engineering_memory/rules.py`：纯确定性 normalization、logical key、context ID、兼容表、状态转换与 projection 规则。
- `src/embedded_copilot/engineering_memory/fingerprint.py`：重新验证后的 canonical JSON、SHA-256 request/snapshot/evidence fingerprint。
- `src/embedded_copilot/engineering_memory/ports.py`：同步 runtime-checkable Memory、Store、Permission 与 Audit Protocol。
- `src/embedded_copilot/engineering_memory/facade.py`：只公开 `memory_port()` 的受控 facade。
- `src/embedded_copilot/engineering_memory/factory.py`：校验三项依赖并装配 service、facade。
- `src/embedded_copilot/engineering_memory/service.py`：实现 strict validation、audit、permission、Store 和 terminal audit 的固定执行链。
- `src/embedded_copilot/engineering_memory/audit.py`：构造稳定 `event_key` 的无工程内容事件并 fail closed 记录。
- `src/embedded_copilot/engineering_memory/exceptions.py`：定义稳定、清洗后的公共异常。
- `src/embedded_copilot/engineering_memory/stores/in_memory.py`：私有 Aggregate 和唯一线程安全 reference Store。
- `src/embedded_copilot/engineering_memory/stores/__init__.py`：stores 子包说明；不公开 adapter。
- `src/embedded_copilot/engineering_memory/__init__.py`：只导出获准的 facade、factory、DTO、exceptions 和 Protocol。

### Test files

- `tests/engineering_memory/__init__.py`：测试包标记，不含共享可变状态。
- `tests/engineering_memory/test_contracts.py`：严格基础模型、record、commands、results、篡改重验证。
- `tests/engineering_memory/test_payloads.py`：八类 payload、provenance、logical key 与安全文本。
- `tests/engineering_memory/test_factory.py`：Protocol 注入、facade 窄接口与严格 exports。
- `tests/engineering_memory/test_mutations.py`：create、revision、receipt、slot uniqueness。
- `tests/engineering_memory/test_state_transitions.py`：Verification、approval、revoke、Verification History、replacement。
- `tests/engineering_memory/test_queries.py`：typed snapshots、排序、fingerprint、revision-bound history。
- `tests/engineering_memory/test_idempotency.py`：operation fingerprint/replay/conflict 和 terminal audit replay。
- `tests/engineering_memory/test_audit.py`：event ordering、event key、无内容、fail-closed sink。
- `tests/engineering_memory/test_permissions.py`：九字段最小披露、echo binding、deny/异常/畸形结果。
- `tests/engineering_memory/test_concurrency.py`：确定性交错、lost update、slot/replacement 原子性。
- `tests/engineering_memory/test_in_memory_store.py`：八方法 Store contract、copy-on-write、Aggregate 隔离和无泄漏。
- `tests/security/test_engineering_memory_boundary.py`：固定文件集合、AST/token gate 和既有 Runtime facade regression。
- `tests/release/test_v039_release.py`：版本、文档、依赖不变、release non-goals 和质量门禁合同。

测试文件保持上述 14 个独立文件，不合并；contracts、state、query、audit、permission、concurrency 和 release 各自具有可单独审查的失败语义，合并会形成难以定位的单体测试。

## Locked Public Contracts

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


class EngineeringMemoryStorePort(Protocol):
    def create_candidate(
        self,
        request: CreateCandidateRequest,
        *,
        request_fingerprint: str,
    ) -> MemoryMutationResult: ...

    def create_replacement_candidate(
        self,
        request: CreateReplacementCandidateRequest,
        *,
        request_fingerprint: str,
    ) -> MemoryMutationResult: ...

    def apply_verification(
        self,
        request: ApplyVerificationRequest,
        *,
        request_fingerprint: str,
    ) -> MemoryMutationResult: ...

    def apply_human_approval(
        self,
        request: ApplyHumanApprovalRequest,
        *,
        request_fingerprint: str,
    ) -> MemoryMutationResult: ...

    def revoke_record(
        self,
        request: RevokeRecordRequest,
        *,
        request_fingerprint: str,
    ) -> MemoryMutationResult: ...

    def get_verified_snapshot(
        self,
        request: GetVerifiedSnapshotRequest,
    ) -> EngineeringMemorySnapshot: ...

    def get_candidate_snapshot(
        self,
        request: GetCandidateSnapshotRequest,
    ) -> EngineeringMemorySnapshot: ...

    def get_history(
        self,
        request: GetHistoryRequest,
    ) -> EngineeringMemoryHistoryPage: ...
```

Store Protocol 不暴露 Aggregate、锁、内部容器、callback、generic save/update/delete 或 CRUD。`MemoryMutationResult` 只含安全标识、outcome、aggregate revision 和受影响记录的 ID/status/revision，因此 operation receipt 能完整重放而不保存 payload。

---

### Task 1: 严格合同基础

**Files:**
- Create: `src/embedded_copilot/engineering_memory/models.py`
- Create: `src/embedded_copilot/engineering_memory/exceptions.py`
- Create: `tests/engineering_memory/__init__.py`
- Create: `tests/engineering_memory/test_contracts.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel`, `ConfigDict`, `AwareDatetime`, `StrEnum`。
- Produces: `_EngineeringMemoryContract`, `_MemoryRequestContract`（五个公共请求字段）, `_MemoryWriteRequestContract`（增加 `operation_id`、`expected_revision`）, `MemoryType`, `MemoryStatus`, `MemoryCommandType`, `MemoryAction`, `MemoryPermissionStatus`, `MemoryAuditEventType`, `MemoryMutationOutcome`, shared validators, and the nine public exception classes from design section 22。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_contract_is_frozen_strict_and_rejects_extra_fields() -> None:
    request = _ReadProbe(
        request_id="req-1", project_id="p1", memory_id="m1",
        caller="caller-1", requested_at=UTC_TIME,
    )
    with pytest.raises(ValidationError):
        request.request_id = "changed"
    with pytest.raises(ValidationError):
        _ReadProbe(**request.model_dump(), unexpected=True)
    with pytest.raises(ValidationError):
        _WriteProbe(**COMMON, operation_id="op-1", expected_revision=True)
    assert tuple(request.model_dump()) == (
        "request_id", "project_id", "memory_id", "caller", "requested_at"
    )


def test_datetime_must_be_aware_and_is_normalized_to_utc() -> None:
    with pytest.raises(ValidationError, match="timezone aware"):
        _ReadProbe(**COMMON, requested_at=datetime(2026, 7, 29))
    value = _ReadProbe(**COMMON, requested_at=PLUS_EIGHT_TIME)
    assert value.requested_at.utcoffset() == timedelta(0)
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_contracts.py -q`

Expected: collection fails with `ModuleNotFoundError: embedded_copilot.engineering_memory`; no unrelated test failure is accepted as RED evidence.

- [ ] **Step 3: Implement the minimal contract foundation**

Use one private base model configured exactly as follows, normalize NFC/trim before regex checks, reject NUL/newlines/absolute paths/secret markers in safe references, and convert every aware datetime with `astimezone(timezone.utc)`:

```python
class _EngineeringMemoryContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True,
        revalidate_instances="always", strict=True,
    )
```

Define enums before any DTO that consumes them. `_MemoryRequestContract` owns exactly `request_id`、`project_id`、`memory_id`、`caller`、`requested_at`; `_MemoryWriteRequestContract` adds non-empty `operation_id` and non-negative strict-int `expected_revision`. Test-only `_ReadProbe`/`_WriteProbe` subclasses exercise these bases without introducing a public command prematurely. Define cleaned exceptions with fixed reason-code messages and empty `__slots__`: `EngineeringMemoryError`, `EngineeringMemoryRequestRejected`, `MemoryPermissionDenied`, `MemoryAuditUnavailable`, `MemoryStoreUnavailable`, `MemoryRevisionConflict`, `MemoryOperationConflict`, `MemoryStateTransitionRejected`, and `MemoryRecordNotFound`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_contracts.py -q`

Expected: all Task 1 tests pass; strict bool-as-int, invalid enum, unsafe identifier, naive datetime and mutated nested-instance cases are covered.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/models.py src/embedded_copilot/engineering_memory/exceptions.py tests/engineering_memory`

Complete when only contract foundation files changed, every enum precedes first use, no clock/UUID/random/environment/filesystem access exists, and no implementation commit is created.

### Task 2: 强类型 Payload 与 Provenance

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/models.py`
- Create: `src/embedded_copilot/engineering_memory/rules.py`
- Create: `tests/engineering_memory/test_payloads.py`

**Interfaces:**
- Consumes: `_EngineeringMemoryContract`, `MemoryType`, `VerificationSubjectType`, safe identifier/reference validators。
- Produces: eight payload DTOs, closed `MemoryPayload`, `MemoryProvenance`, `MemorySourceType`, and `logical_key_for(payload: MemoryPayload) -> str`。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_pin_logical_key_uses_only_target_and_pin() -> None:
    left = PinBindingMemory(memory_type=MemoryType.PIN_BINDING,
        target_id="mcu1", pin_id="GPIO4", function="SDA",
        component_reference="u1", interface_reference="i2c0")
    right = left.model_copy(update={"component_reference": "u2"})
    assert logical_key_for(left) == logical_key_for(right) == "pin:mcu1:GPIO4"


def test_payloads_reject_untyped_dict_and_unsafe_provenance() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(MemoryPayload).validate_python(
            {"memory_type": "BOARD_PROFILE"}, strict=True
        )
    with pytest.raises(ValidationError, match="unsafe"):
        MemoryProvenance(**PROVENANCE_DATA, source_reference="C:/secret.env")
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_payloads.py -q`

Expected: import errors name `BoardProfileMemory`, `MemoryProvenance`, or `logical_key_for` because payload contracts do not exist yet.

- [ ] **Step 3: Implement the minimal payload and logical-key rules**

Create discriminator-backed DTOs with the exact design fields. Use integer millivolts/milliamps, enforce `minimum_voltage_mv <= maximum_voltage_mv`, reject arbitrary dict payloads, sort/deduplicate `finding_categories`, and compute only these keys:

```python
KEY_BUILDERS = {
    MemoryType.BOARD_PROFILE: lambda p: "board-profile",
    MemoryType.COMPONENT: lambda p: f"component:{p.component_reference}",
    MemoryType.PIN_BINDING: lambda p: f"pin:{p.target_id}:{p.pin_id}",
    MemoryType.INTERFACE_BINDING: lambda p: f"interface:{p.target_id}:{p.interface_id}:{p.signal}",
    MemoryType.POWER_CONSTRAINT: lambda p: f"power:{p.supply_id}:{p.load_id}",
    MemoryType.ENGINEERING_DECISION: lambda p: f"decision:{p.decision_topic}",
    MemoryType.KNOWN_ISSUE: lambda p: f"issue:{p.issue_key}",
    MemoryType.VERIFICATION_HISTORY: lambda p: f"verification:{p.verification_request_id}",
}
```

`MemoryProvenance` uses exactly `source_type`, `source_reference`, `source_revision`, `created_by`, `observed_at`; reference validators reject paths, secret-like text, source/log bodies and line breaks.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_payloads.py tests/engineering_memory/test_contracts.py -q`

Expected: all eight payloads, stable keys, duplicate tuple rejection, provenance immutability, safe references and numeric boundaries pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/models.py src/embedded_copilot/engineering_memory/rules.py tests/engineering_memory/test_payloads.py`

Complete when logical keys depend only on approved stable fields, Verification History identity is `verification:<verification_request_id>`, and payload/provenance cannot enter generic dict storage.

### Task 3: Record、State History 与 Evidence

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/models.py`
- Modify: `src/embedded_copilot/engineering_memory/rules.py`
- Modify: `tests/engineering_memory/test_contracts.py`

**Interfaces:**
- Consumes: payloads, provenance, `MemoryStatus`, v0.38 `VerificationRequest`/`VerificationResult`。
- Produces: `MemoryStateTransition`, `VerificationEvidenceBinding`, `HumanApprovalEvidence`, `EngineeringMemoryRecord`, `memory_context_id(project_id, memory_id, record_id, record_revision) -> str`。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_new_record_has_candidate_revision_zero_and_initial_history() -> None:
    record = build_candidate_record(CREATE, aggregate_revision=1)
    assert record.status is MemoryStatus.CANDIDATE
    assert record.record_revision == 0
    assert [(t.from_status, t.to_status) for t in record.state_history] == [
        (None, MemoryStatus.CANDIDATE)
    ]


def test_memory_context_id_binds_record_revision() -> None:
    assert memory_context_id("p1", "m1", "r1", 3) == "memory:p1:m1:r1:3"
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_contracts.py -q`

Expected: `ImportError` for record/evidence DTOs or `NameError` for `build_candidate_record`.

- [ ] **Step 3: Implement the minimal immutable record model**

Define evidence and transition DTOs before `EngineeringMemoryRecord`. The record contains all fields from design section 7 and validates revision/history consistency. `build_candidate_record` derives internal fields; public create requests never expose `status`, `logical_key`, revisions, history or evidence bindings. Each transition uses command `requested_at`, and state history is an append-only tuple. `VerificationEvidenceBinding` stores only request ID, subject, status, request/result fingerprints, requested time and safe summary reference; `HumanApprovalEvidence` uses the exact six approved fields.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_contracts.py -q`

Expected: freeze, initial transition, deterministic context binding, evidence revalidation and caller-controlled internal-field rejection pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/models.py src/embedded_copilot/engineering_memory/rules.py tests/engineering_memory/test_contracts.py`

Complete when the only initial state is `CANDIDATE`, new records are revision 0, later transitions require exactly `+1`, and no mutable history or internal-state constructor path is public.

### Task 4: Commands、Results 与 Fingerprint

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/models.py`
- Create: `src/embedded_copilot/engineering_memory/fingerprint.py`
- Modify: `tests/engineering_memory/test_contracts.py`

**Interfaces:**
- Consumes: all payload/record/evidence types and v0.38 Verification contracts。
- Produces: eight command DTOs, closed `EngineeringMemoryRequest`, nine-field `MemoryAuthorizationRequest`, echo-bound `MemoryPermissionDecision`, content-free `MemoryAuditEvent`, `AffectedMemoryRecord`, `MemoryMutationResult`, `MemorySnapshotRecord`, `EngineeringMemorySnapshot`, `EngineeringMemoryHistoryPage`, closed `EngineeringMemoryResult`, `canonical_fingerprint(model) -> str`。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_canonical_fingerprint_is_stable_for_unicode_and_field_order() -> None:
    first = CreateCandidateRequest(**CREATE_DATA)
    second = CreateCandidateRequest.model_validate(dict(reversed(tuple(CREATE_DATA.items()))))
    assert canonical_fingerprint(first) == canonical_fingerprint(second)
    assert canonical_fingerprint(first).startswith("sha256:")


def test_history_cursor_and_result_are_strict_and_content_bounded() -> None:
    with pytest.raises(ValidationError):
        GetHistoryRequest(**COMMON, cursor="offset:1")
    assert "payload" not in MemoryMutationResult.model_fields


def test_authorization_contract_has_exactly_nine_request_fields() -> None:
    assert tuple(MemoryAuthorizationRequest.model_fields) == (
        "request_id", "operation_id", "project_id", "memory_id", "caller",
        "command_type", "action", "request_fingerprint", "requested_at",
    )
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_contracts.py -q`

Expected: missing command/result types and fingerprint function cause collection failure.

- [ ] **Step 3: Implement the minimal commands, results and canonical hash**

Use a discriminated closed request union keyed by `command_type`. All writes have non-empty `operation_id` and non-negative `expected_revision`; reads have neither. Cursor format is fixed as `revision:<aggregate_revision>:offset:<n>`; both numeric segments must parse as non-negative decimal integers, with limit `1..100` default 50. Fingerprint implementation is exact:

```python
validated = type(value).model_validate(copy.deepcopy(value.model_dump(mode="python")))
encoded = json.dumps(validated.model_dump(mode="json"), ensure_ascii=False,
    sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
return "sha256:" + hashlib.sha256(encoded).hexdigest()
```

Define authorization, decision and audit DTOs before Task 5 Protocol declarations. Authorization contains exactly the nine locked fields; decision echoes all nine and adds only decision/reason code; audit contains only its locked safe metadata. Mutation results contain request/operation/command/outcome/affected records/aggregate revision only. Snapshot/history types return frozen records, never internal Aggregate objects.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_contracts.py tests/engineering_memory/test_payloads.py -q`

Expected: discriminators, context binding, UTF-8/stable ordering/compact separators, tampered nested revalidation, cursor grammar and result-content boundaries pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/models.py src/embedded_copilot/engineering_memory/fingerprint.py tests/engineering_memory/test_contracts.py`

Complete when all public types are defined before first use, request/result unions are closed, and receipts can replay mutation results without payload or evidence bodies.

### Task 5: Ports、Facade、Factory 与严格导出

**Files:**
- Create: `src/embedded_copilot/engineering_memory/ports.py`
- Create: `src/embedded_copilot/engineering_memory/facade.py`
- Create: `src/embedded_copilot/engineering_memory/factory.py`
- Create: `src/embedded_copilot/engineering_memory/service.py`
- Create: `src/embedded_copilot/engineering_memory/audit.py`
- Create: `src/embedded_copilot/engineering_memory/stores/__init__.py`
- Create: `src/embedded_copilot/engineering_memory/__init__.py`
- Create: `tests/engineering_memory/test_factory.py`

**Interfaces:**
- Consumes: Task 4 requests/results/permission/audit DTOs and Task 1 exceptions。
- Produces: the locked factory/facade/Memory/Permission/Audit interfaces and exact eight-method `EngineeringMemoryStorePort` shown above。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_facade_and_ports_are_narrow() -> None:
    memory = create_engineering_memory(store=STORE, permission_port=PERMISSION, audit_sink=AUDIT)
    assert public_methods(type(memory)) == {"memory_port"}
    assert public_methods(EngineeringMemoryPort) == {"execute"}
    assert public_methods(EngineeringMemoryStorePort) == {
        "create_candidate", "create_replacement_candidate", "apply_verification",
        "apply_human_approval", "revoke_record", "get_verified_snapshot",
        "get_candidate_snapshot", "get_history",
    }


def test_factory_rejects_invalid_dependencies_without_defaults() -> None:
    with pytest.raises(TypeError, match="store"):
        create_engineering_memory(store=object(), permission_port=PERMISSION, audit_sink=AUDIT)
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_factory.py -q`

Expected: package import fails because facade, ports and factory have not been created.

- [ ] **Step 3: Implement the minimal composition shell**

Mark all four Protocols `@runtime_checkable`, use only synchronous methods, and copy the locked signatures verbatim. `EngineeringMemory.__init__` raises so only `_compose` can create it. Factory validates all dependencies and rejects async methods. Build a private `_EngineeringMemoryPort` service shell whose `execute` initially performs request revalidation then dispatches to the eight Store methods; later Task 11 adds audit/permission orchestration. `__all__` lists only approved public contracts and excludes service, rules, helpers, Aggregate, locks, containers and `InMemoryEngineeringMemoryStore`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_factory.py tests/engineering_memory/test_contracts.py -q`

Expected: valid fakes compose, invalid/async/missing dependencies fail, facade has one method, Store has exactly eight methods and strict exports pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory tests/engineering_memory/test_factory.py`

Complete when no default permission exists, no internal Store implementation is exported, and the public entry remains one synchronous `execute()` method.

### Task 6: InMemory Store 聚合与基础 Mutation

**Files:**
- Create: `src/embedded_copilot/engineering_memory/stores/in_memory.py`
- Modify: `src/embedded_copilot/engineering_memory/rules.py`
- Create: `tests/engineering_memory/test_mutations.py`
- Create: `tests/engineering_memory/test_in_memory_store.py`

**Interfaces:**
- Consumes: five mutation request DTOs, three query DTOs, `MemoryMutationResult`, logical-key and candidate-record rules。
- Produces: private `_Aggregate`, `_OperationReceipt`, copy-on-write helpers and `InMemoryEngineeringMemoryStore` satisfying the eight-method Store Protocol。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_receipt_replay_precedes_revision_check() -> None:
    first = STORE.create_candidate(CREATE_R0, request_fingerprint=FP)
    replay = STORE.create_candidate(CREATE_R0, request_fingerprint=FP)
    assert replay == first
    assert STORE.get_candidate_snapshot(READ).aggregate_revision == 1


def test_same_operation_with_different_fingerprint_conflicts() -> None:
    STORE.create_candidate(CREATE_R0, request_fingerprint=FP)
    with pytest.raises(MemoryOperationConflict):
        STORE.create_candidate(CHANGED_CREATE_R0, request_fingerprint=OTHER_FP)
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_mutations.py tests/engineering_memory/test_in_memory_store.py -q`

Expected: import failure for the in-memory adapter or `NotImplementedError` from the service shell.

- [ ] **Step 3: Implement the minimal lock-protected Store operation**

Each Store owns a private dict and `threading.RLock`. For each mutation, enter the same lock-protected Store critical section, load logical revision 0 when absent, check receipt first, then expected revision, precompute a replacement Aggregate value, update projections and receipt, increment aggregate revision exactly once, and replace the dict entry once. Duplicate record ID or occupied normal candidate slot raises a cleaned state exception. No public `clear`, `delete`, `truncate`, raw save/update, callback or container accessor is added.

```python
with self._lock:
    aggregate = self._aggregates.get(key, _empty_aggregate(key))
    replay = _match_receipt(aggregate, request.operation_id, request_fingerprint)
    if replay is not None:
        return _validated_result(replay.result)
    _require_revision(aggregate, request.expected_revision)
    updated, result = _create_candidate(aggregate, request, request_fingerprint)
    self._aggregates[key] = updated
    return _validated_result(result)
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_mutations.py tests/engineering_memory/test_in_memory_store.py -q`

Expected: revision 0 creation, new aggregate revision 1, receipt replay, fingerprint conflict, duplicate IDs/slots, copy-on-write and private-container tests pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/stores/in_memory.py src/embedded_copilot/engineering_memory/rules.py tests/engineering_memory/test_mutations.py tests/engineering_memory/test_in_memory_store.py`

Complete when every domain mutation uses one lock-protected Store critical section and receipt/revision/projection/result/receipt-write cannot be observed partially.

### Task 7: Snapshot 与 Revision-bound History

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/stores/in_memory.py`
- Modify: `src/embedded_copilot/engineering_memory/fingerprint.py`
- Create: `tests/engineering_memory/test_queries.py`
- Modify: `tests/engineering_memory/test_in_memory_store.py`

**Interfaces:**
- Consumes: Store projections and three query requests。
- Produces: verified/candidate typed snapshots, stable snapshot fingerprint, and revision-bound history pages。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_history_cursor_binds_first_page_revision() -> None:
    first = STORE.get_history(GetHistoryRequest(**READ_DATA, limit=1))
    assert first.next_cursor == "revision:2:offset:1"
    STORE.create_candidate(NEXT_CREATE, request_fingerprint=NEXT_FP)
    with pytest.raises(MemoryRevisionConflict):
        STORE.get_history(GetHistoryRequest(**READ_DATA, limit=1, cursor=first.next_cursor))


def test_verified_and_candidate_snapshots_are_isolated_and_sorted() -> None:
    assert tuple(r.logical_key for r in candidate.records) == tuple(sorted(keys))
    assert verified.records == ()
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_queries.py -q`

Expected: query methods lack typed projection/history implementation or return incomplete DTOs.

- [ ] **Step 3: Implement the minimal query behavior**

Read under the Store lock, deep-copy then revalidate every returned DTO. Verified snapshot reads only `active_verified_by_logical_key`; candidate snapshot reads only `candidate_by_logical_key`; Board Profile cardinality is at most one. Sort snapshot records by `(logical_key, record_id)` and history by `(created_aggregate_revision, record_id)`. First history page binds current aggregate revision and offset 0; later pages require exact revision equality before slicing. Emit next cursor only when more records remain. Do not add search, filter, fuzzy, full-text or vector APIs.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_queries.py tests/engineering_memory/test_in_memory_store.py -q`

Expected: isolation, typed categories, sorting, default/range limits, exact cursor grammar, stale cursor conflict, snapshot hash and immutable result tests pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/stores/in_memory.py src/embedded_copilot/engineering_memory/fingerprint.py tests/engineering_memory/test_queries.py tests/engineering_memory/test_in_memory_store.py`

Complete when pagination cannot repeat or omit across a concurrent revision change, and no internal Aggregate/container/reference escapes.

### Task 8: Verification 状态转换

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/rules.py`
- Modify: `src/embedded_copilot/engineering_memory/stores/in_memory.py`
- Create: `tests/engineering_memory/test_state_transitions.py`

**Interfaces:**
- Consumes: `ApplyVerificationRequest`, v0.38 frozen request/result, record/context/fingerprint helpers。
- Produces: exact subject compatibility matrix and PASS/FAIL/REVIEW_REQUIRED transitions。

- [ ] **Step 1: Write the failing RED tests**

```python
@pytest.mark.parametrize("status,expected", [
    (VerificationStatus.PASS, MemoryStatus.VERIFIED),
    (VerificationStatus.FAIL, MemoryStatus.REJECTED),
    (VerificationStatus.REVIEW_REQUIRED, MemoryStatus.CANDIDATE),
])
def test_verification_status_maps_deterministically(status, expected) -> None:
    result = STORE.apply_verification(make_verification(status), request_fingerprint=FP)
    affected = result.affected_records[0]
    assert affected.status is expected
    assert affected.record_revision == 1
    assert result.aggregate_revision == 2


def test_review_required_appends_candidate_self_transition() -> None:
    STORE.apply_verification(REVIEW_REQUEST, request_fingerprint=FP)
    record = only_history_record(STORE)
    assert (record.state_history[-1].from_status, record.state_history[-1].to_status) == (
        MemoryStatus.CANDIDATE, MemoryStatus.CANDIDATE)
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_state_transitions.py -q`

Expected: `apply_verification` rejects unimplemented transitions or cannot build verification binding.

- [ ] **Step 3: Implement the minimal Verification rules**

Revalidate both nested v0.38 objects, match request/result IDs, exact `memory:<project>:<memory>:<record>:<revision>` context, record revision, and final-result binding. Enforce `HARDWARE` only for Board/Component/Pin/Interface/Power; all three subjects for Decision/Issue; exact payload subject for Verification History. PASS maps to VERIFIED, FAIL to REJECTED, and REVIEW_REQUIRED appends `CANDIDATE -> CANDIDATE`, stores the binding, increments record and aggregate revision once, and writes the receipt in the same lock-protected Store critical section. Never instantiate or call Verification Agent.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_state_transitions.py -q`

Expected: compatibility table, request/result/context/revision binding, duplicate verification use, all three transitions and receipt persistence pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/rules.py src/embedded_copilot/engineering_memory/stores/in_memory.py tests/engineering_memory/test_state_transitions.py`

Complete when `FAIL` means the proposal failed rules rather than confirmed hardware failure, and REVIEW_REQUIRED has a persisted self-transition with both revisions incremented.

### Task 9: Human Approval、Revoke 与 VerificationHistory

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/rules.py`
- Modify: `src/embedded_copilot/engineering_memory/stores/in_memory.py`
- Modify: `tests/engineering_memory/test_state_transitions.py`

**Interfaces:**
- Consumes: approval/revoke requests, approval evidence, Verification History payload identity set。
- Produces: restricted approval, revoke transitions and append-only Verification History behavior。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_human_approval_is_limited_to_decision_and_issue() -> None:
    with pytest.raises(MemoryStateTransitionRejected):
        STORE.apply_human_approval(APPROVE_PIN, request_fingerprint=FP)


def test_verification_history_is_append_only_identity() -> None:
    STORE.create_candidate(HISTORY_CREATE, request_fingerprint=FP)
    with pytest.raises(MemoryStateTransitionRejected):
        STORE.create_candidate(HISTORY_CREATE_NEW_OPERATION, request_fingerprint=FP2)
    with pytest.raises(MemoryStateTransitionRejected):
        STORE.create_replacement_candidate(HISTORY_REPLACEMENT, request_fingerprint=FP3)
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_state_transitions.py -q`

Expected: approval/revoke methods are incomplete and duplicate history identity is not yet rejected.

- [ ] **Step 3: Implement the minimal approval, revoke and history rules**

Approval only accepts Decision/Issue candidates, exact record/revision evidence binding and Aggregate-unique approval ID. Revoke permits only CANDIDATE or VERIFIED to REVOKED and leaves history intact. Maintain a separate `verification_request_ids` set populated on first Verification History creation; never remove it. Reject replacement/approval for Verification History and exclude it from normal slot projections. All successful changes append one transition, increment record/aggregate revisions, update projections and save receipt in the same lock-protected Store critical section. Add no recovery or hard-delete path.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_state_transitions.py tests/engineering_memory/test_mutations.py -q`

Expected: approval allowlist, approval ID/revision binding, revoke legality, terminal-state rejection and append-only identity tests pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/rules.py src/embedded_copilot/engineering_memory/stores/in_memory.py tests/engineering_memory/test_state_transitions.py`

Complete when technical facts cannot bypass Verification, Verification History never participates in replacement/approval, and revoked/rejected/superseded records cannot be restored.

### Task 10: 延迟原子替代

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/rules.py`
- Modify: `src/embedded_copilot/engineering_memory/stores/in_memory.py`
- Modify: `tests/engineering_memory/test_state_transitions.py`
- Create: `tests/engineering_memory/test_concurrency.py`

**Interfaces:**
- Consumes: replacement request, verification/approval activation and Store projection helpers。
- Produces: delayed replacement candidate and atomic dual-record activation。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_replacement_activates_both_records_in_one_aggregate_revision() -> None:
    before = STORE.get_verified_snapshot(READ)
    result = STORE.apply_verification(REPLACEMENT_PASS, request_fingerprint=FP)
    old, new = records_by_id(STORE, "old", "new")
    assert old.status is MemoryStatus.SUPERSEDED
    assert new.status is MemoryStatus.VERIFIED
    assert old.record_revision == 2 and new.record_revision == 1
    assert result.aggregate_revision == before.aggregate_revision + 1


def test_concurrent_replacement_activation_has_exactly_one_winner() -> None:
    outcomes = run_with_barrier(ACTIVATE_A, ACTIVATE_B)
    assert count_success(outcomes) == 1
    assert count_exception(outcomes, MemoryRevisionConflict) == 1
    assert active_verified_count(STORE, LOGICAL_KEY) == 1
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_state_transitions.py tests/engineering_memory/test_concurrency.py -q`

Expected: old projection remains active after PASS or concurrency exposes multiple winners before atomic activation exists.

- [ ] **Step 3: Implement the minimal delayed atomic replacement**

Creation requires the current active VERIFIED record ID and same normal logical key, but leaves old VERIFIED active. On PASS or permitted approval, precompute both immutable records: old `VERIFIED -> SUPERSEDED`, new `CANDIDATE -> VERIFIED`, reciprocal binding, each record revision `+1`; switch verified/candidate projections, increment aggregate revision once and save one receipt. Publish the new Aggregate only after every check succeeds, all within the same lock-protected Store critical section. FAIL, REVIEW_REQUIRED and REVOKED leave the old record active. Use `threading.Barrier`/`Event` in tests, never `sleep()`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_state_transitions.py tests/engineering_memory/test_concurrency.py -q`

Expected: delayed visibility, PASS/approval activation, non-activation outcomes, one aggregate increment, both record revisions, exactly-one concurrent winner and no partial state pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/rules.py src/embedded_copilot/engineering_memory/stores/in_memory.py tests/engineering_memory/test_state_transitions.py tests/engineering_memory/test_concurrency.py`

Complete when no observation can contain two current VERIFIED records for one logical slot or half of a replacement, and SUPERSEDED is never auto-restored.

### Task 11: Permission 与 Audit 执行链

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/service.py`
- Modify: `src/embedded_copilot/engineering_memory/audit.py`
- Create: `tests/engineering_memory/test_permissions.py`
- Create: `tests/engineering_memory/test_audit.py`
- Modify: `tests/engineering_memory/test_idempotency.py`

**Interfaces:**
- Consumes: canonical request fingerprint, all eight Store methods, Permission/Audit Protocols and cleaned exceptions。
- Produces: nine-field `MemoryAuthorizationRequest`, echo-bound `MemoryPermissionDecision`, content-free `MemoryAuditEvent`, fixed service execution chain。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_permission_receives_only_nine_bound_fields() -> None:
    PORT.execute(CREATE)
    assert tuple(PERMISSION.requests[0].model_fields) == (
        "request_id", "operation_id", "project_id", "memory_id", "caller",
        "command_type", "action", "request_fingerprint", "requested_at",
    )


def test_terminal_audit_failure_replay_does_not_repeat_mutation() -> None:
    with pytest.raises(MemoryAuditUnavailable):
        PORT.execute(CREATE)
    assert STORE.mutation_count == 1
    result = PORT.execute(CREATE)
    assert STORE.mutation_count == 1
    assert AUDIT.attempted_terminal_keys == (TERMINAL_KEY, TERMINAL_KEY)
    assert AUDIT.logical_event_count(TERMINAL_KEY) == 1
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_permissions.py tests/engineering_memory/test_audit.py tests/engineering_memory/test_idempotency.py -q`

Expected: service does not yet emit requested/terminal events or authorize the minimal fingerprint-bound DTO.

- [ ] **Step 3: Implement the minimal fixed execution chain**

Execute exactly: revalidate/deep-copy request; fingerprint; `MEMORY_REQUESTED`; construct minimal authorization; authorize and revalidate/echo-match every field; dispatch Store; emit terminal event; return revalidated result. Map command to one `MemoryAction` internally. Use event keys `memory-audit:<request_id>:<operation_id>:<event_type>` for writes and `memory-audit:<request_id>:<event_type>` for reads; timestamp reuses `requested_at`. Permission deny/revision/operation/state/request conflicts emit REJECTED; adapter/internal failures emit FAILED. Requested audit failure calls neither permission nor Store. Terminal failure after mutation does not roll back or deliver result; replay reaches the same Store receipt and retries the same event key without mutation.

`MemoryAuditEvent` contains only event key/type, request ID, optional operation ID, project/memory IDs, optional record ID, command type and timestamp. Permission contains exactly the nine fields in the test; neither DTO includes payload, provenance, Finding, full Verification/Approval, path, log, source or exception text.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory/test_permissions.py tests/engineering_memory/test_audit.py tests/engineering_memory/test_idempotency.py -q`

Expected: ordering, minimum disclosure, echo mismatch, deny, permission/store/sink exceptions, all terminal types, stable event keys, query terminal failure and mutation replay pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/service.py src/embedded_copilot/engineering_memory/audit.py tests/engineering_memory/test_permissions.py tests/engineering_memory/test_audit.py tests/engineering_memory/test_idempotency.py`

Complete when no partial result is returned after any failure, permission sees only nine fields, and terminal audit retry is logically idempotent without a second Store mutation.

### Task 12: 并发、输入隔离与 Store Contract

**Files:**
- Modify: `src/embedded_copilot/engineering_memory/service.py`
- Modify: `src/embedded_copilot/engineering_memory/stores/in_memory.py`
- Modify: `tests/engineering_memory/test_concurrency.py`
- Modify: `tests/engineering_memory/test_in_memory_store.py`
- Modify: `tests/engineering_memory/test_contracts.py`

**Interfaces:**
- Consumes: finalized Store Port, copy-on-write Aggregate and public DTO validators。
- Produces: deterministic concurrency guarantees and boundary input/output isolation。

- [ ] **Step 1: Write the failing RED tests**

```python
def test_two_writes_at_same_revision_have_one_success() -> None:
    outcomes = run_with_barrier(CREATE_A_R0, CREATE_B_R0)
    assert count_success(outcomes) == 1
    assert count_exception(outcomes, MemoryRevisionConflict) == 1
    assert STORE.get_candidate_snapshot(READ).aggregate_revision == 1


def test_mutated_nested_input_cannot_change_stored_record() -> None:
    raw = CREATE.model_construct(payload=TAMPERED_PAYLOAD, **UNSAFE_INTERNALS)
    with pytest.raises(EngineeringMemoryRequestRejected):
        PORT.execute(raw)
    assert STORE.get_history(HISTORY_READ).records == ()
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/engineering_memory/test_concurrency.py tests/engineering_memory/test_in_memory_store.py tests/engineering_memory/test_contracts.py -q`

Expected: one isolation/concurrency assertion fails until every boundary performs deep-copy revalidation and all mutation paths share the Store lock.

- [ ] **Step 3: Implement the minimal isolation guarantees**

At service input, permission output, Store input and public result output, use `model_dump(mode="python")`, deep copy and target-type `model_validate`. Keep all instance state private, prohibit module-level mutable dict/list/set, and return only frozen copies. All race tests use Barrier/Event-controlled starts. Add an introspection test that the Store Protocol exposes exactly eight methods and the facade cannot expose lock, Aggregate, receipts or container identities.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/engineering_memory -q`

Expected: the entire Memory suite passes, including different-Aggregate isolation, no lost update, no duplicate VERIFIED slot, no partial replacement and nested tamper rejection.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory tests/engineering_memory`

Complete when public inputs/outputs share no mutable Store identity, no lock or internal state is observable, and deterministic synchronization tests pass without timing sleeps.

### Task 13: Security AST Boundary

**Files:**
- Create: `tests/security/test_engineering_memory_boundary.py`
- Modify: `src/embedded_copilot/engineering_memory/__init__.py`

**Interfaces:**
- Consumes: final package tree and existing Runtime facades。
- Produces: fixed package allowlist and static capability boundary gate。

- [ ] **Step 1: Write the failing RED tests**

```python
ROOT_FILES = {"__init__.py", "audit.py", "exceptions.py", "facade.py", "factory.py",
              "fingerprint.py", "models.py", "ports.py", "rules.py", "service.py"}
STORE_FILES = {"__init__.py", "in_memory.py"}

def test_engineering_memory_package_is_fixed_and_non_executing() -> None:
    assert {p.name for p in PACKAGE.glob("*.py")} == ROOT_FILES
    assert {p.name for p in (PACKAGE / "stores").glob("*.py")} == STORE_FILES
    assert_forbidden_imports_calls_tokens_and_mutable_module_state_are_absent(PACKAGE)


def test_existing_runtime_facades_remain_unchanged() -> None:
    assert facade_methods() == EXPECTED_V038_FACADE_METHODS
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/security/test_engineering_memory_boundary.py -q`

Expected: strict export/token/file-set assertions expose any unapproved symbol or the new test initially fails before the approved allowlist is finalized.

- [ ] **Step 3: Implement the minimal static gates and export correction**

Parse every package file with `ast`. Reject imports/calls/tokens for Agent/Supervisor/Model/LLM/RAG/API/Streamlit, Tool execution, Workspace mutation, Debug hardware access, Shell/subprocess/Git, network/database/filesystem/environment/cache/persistence, async/background/dynamic import/eval/exec, `os.system`, `Popen`, UUID/random/system clock, hard delete/clear/truncate, default allow and caller-supplied VERIFIED/SUPERSEDED. Allow `threading` only in `stores/in_memory.py` and public Verification contract imports only in `models.py`; forbid Verification Agent construction/call. Regress Reasoning, Coding, Workspace, VS Code, Debug, Telemetry, Tool and Verification facades.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/security/test_engineering_memory_boundary.py tests/security/test_verification_agent_boundary.py tests/security/test_tool_runtime_boundary.py tests/security/test_workspace_runtime_boundary.py tests/security/test_coding_runtime_boundary.py -q`

Expected: fixed file set, AST/call/token gates, narrow facade/ports/exports and existing Runtime boundary regression all pass.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- src/embedded_copilot/engineering_memory/__init__.py tests/security/test_engineering_memory_boundary.py`

Complete when only approved public contracts export, InMemory adapter stays internal, and no execution/persistence/write capability crosses the Memory boundary.

### Task 14: 版本、文档与 Release Contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/embedded_copilot/__init__.py`
- Modify: `src/embedded_copilot/core/config.py`
- Modify: `src/embedded_copilot/schemas/api.py`
- Modify: `tests/config/test_model_runtime_settings.py`
- Modify: `tests/api/test_routes.py`
- Modify: `tests/services/test_config.py`
- Modify: `tests/services/test_engineering_runtime.py`
- Modify: `tests/supervisor/test_public_contract_compatibility.py`
- Modify: `tests/release/test_contract_compatibility.py`
- Modify: `tests/release/test_release_metadata.py` (historical dirty overlap; HEAD-based index-only update)
- Modify: `tests/release/test_v038_release.py`
- Create: `tests/release/test_v039_release.py`
- Modify: `README.md` (historical dirty overlap; HEAD-based index-only update)
- Modify: `docs/architecture.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Create: `docs/release/v0.39.0.md`

**Interfaces:**
- Consumes: complete public contract and verified v0.39 feature facts。
- Produces: synchronized `0.39.0` metadata, historical compatibility assertions and release documentation。

- [ ] **Step 1: Write the failing RED release tests**

```python
def test_v039_versions_are_synchronized() -> None:
    assert project_version() == package_version() == Settings().version == "0.39.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.39.0"


def test_v039_release_documents_security_and_quality_scope() -> None:
    text = Path("docs/release/v0.39.0.md").read_text(encoding="utf-8")
    for phrase in ("contract-first", "InMemory", "candidate", "VERIFIED",
                   "Workspace Runtime", "Black 26.5.1", "181"):
        assert phrase in text
```

- [ ] **Step 2: Run RED and verify the expected failure**

Run: `python -m pytest tests/release/test_v039_release.py tests/release/test_contract_compatibility.py tests/release/test_release_metadata.py -q`

Expected: v0.39 release document is absent and current version remains `0.38.0`.

- [ ] **Step 3: Implement the minimal release metadata and documentation**

Set pyproject/package/Settings/Health to `0.39.0`; update exact version assertions in config/API/service/supervisor compatibility tests. Preserve v0.38 historical documentation/dependency assertions but remove only its stale “current version is 0.38.0” test. Release note states contract-first, InMemory reference Store, candidate/verified isolation, deterministic transitions, no real persistence, no Agent/LLM/RAG, no file/Tool/hardware operation, no hard delete, Workspace unique write boundary, staged-change Black gate and 181 historical Black differences as separate debt.

Update PROJECT_CONTEXT to Current v0.39.0, Latest Completed Engineering Memory Layer, Current Tag v0.39.0, Next Version `not yet approved`; do not invent a self-referential commit SHA—state that the annotated tag/Git supplies the release commit reference. Add Tool Runtime, Verification Agent and Engineering Memory to completed history, with v0.37/v0.38/v0.39 Completed. README and release metadata changes must later be built from HEAD content into the index, never from their dirty worktree copies.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/release/test_v039_release.py tests/release/test_contract_compatibility.py tests/release/test_release_metadata.py tests/release/test_v038_release.py tests/config/test_model_runtime_settings.py tests/api/test_routes.py tests/services/test_config.py tests/services/test_engineering_runtime.py tests/supervisor/test_public_contract_compatibility.py -q`

Expected: all v0.39/current-version and preserved historical assertions pass with dependency list unchanged.

- [ ] **Step 5: Review the task diff and completion condition**

Run: `git diff -- pyproject.toml src/embedded_copilot/__init__.py src/embedded_copilot/core/config.py src/embedded_copilot/schemas/api.py tests docs/architecture.md docs/PROJECT_CONTEXT.md docs/release/v0.39.0.md`

For README and `tests/release/test_release_metadata.py`, review generated HEAD-to-target patches separately. Complete when version literals are synchronized, docs contain only implemented claims, old release history remains, and historical dirty text is untouched in the worktree.

### Task 15: Focused、Regression 与 Full Validation

**Files:**
- Test: all files listed in Tasks 1–14, executed from an exported candidate staged tree。
- Create temporarily outside repository: candidate index, staged-tree archive/export directory, staged Python manifest。

**Interfaces:**
- Consumes: explicit v0.39 candidate file list and execution-preflight Python command。
- Produces: verified candidate tree hash and complete gate log for Task 16。

- [ ] **Step 1: Prepare the validation RED negative control**

Create a new empty temporary directory outside the repository and make it the current directory without copying any worktree files. This negative control proves that the validation command cannot accidentally discover the repository through the working directory.

- [ ] **Step 2: Run RED and verify the expected failure**

Run from that empty directory: `python -m pytest tests/engineering_memory -q`

Expected: pytest exits nonzero with `file or directory not found: tests/engineering_memory`. Any imported repository test indicates path leakage and must be corrected before candidate-tree validation.

- [ ] **Step 3: Implement the minimal staged-tree validation pipeline**

Create a temporary index initialized from execution-start HEAD, apply the explicit v0.39 file list plus HEAD-based index-only patches, run `git write-tree`, and export that exact tree with `git archive --output <archive> <tree-hash>` into a new temporary directory. Generate the Black manifest only from candidate-index `git diff --cached --name-only --diff-filter=ACMR <baseline>`, filter `*.py`, sort uniquely and require each entry to exist in the export. Preserve the candidate tree hash and all command output. Never copy validation inputs from the working tree.

- [ ] **Step 4: Run GREEN on the exact exported staged tree**

From the exported staged tree, run in this exact order:

```powershell
python -m pytest tests/engineering_memory -q
python -m pytest tests/security/test_engineering_memory_boundary.py -q
python -m pytest tests/release/test_v039_release.py tests/release/test_contract_compatibility.py tests/release/test_release_metadata.py -q
python -m pytest tests/test_verification_agent.py tests/security/test_verification_agent_boundary.py -q
python -m pytest tests/test_tool_runtime.py tests/security/test_tool_runtime_boundary.py -q
python -m pytest tests/test_workspace_runtime.py tests/security/test_workspace_runtime_boundary.py -q
python -m pytest tests/test_coding_runtime.py tests/security/test_coding_runtime_boundary.py -q
python -m pytest tests/test_debug_runtime.py tests/security/test_debug_runtime_boundary.py -q
python -m pytest tests/test_telemetry_runtime.py tests/security/test_telemetry_runtime_boundary.py -q
python -m pytest tests/test_vscode_runtime.py tests/security/test_vscode_runtime_boundary.py -q
python -m pytest tests/reasoning_runtime tests/security/test_reasoning_runtime_boundary.py -q
python -m pytest -q
python -m ruff check .
python -m compileall -q src tests
python -m pip check
```

Then run Black 26.5.1 against the generated manifest:

```powershell
python -m black --check <manifest paths>
```

Expected: every command exits 0; Black reports no changes and its preflight version is 26.5.1. Run `git diff --cached --check`, cached-name review, full cached diff review and a second `git write-tree` on the candidate index; require exact approved names and stable tree hash. Stop at the first failure, update only the responsible v0.39 candidate-index input, re-export a new tree, and restart the entire GREEN order. The manifest excludes worktree-only historical dirty files and the 181-file repository debt.

- [ ] **Step 5: Review the validation diff and completion condition**

Run: `git diff --stat <baseline>` and inspect every candidate-index patch, especially README/release metadata HEAD-based hunks and excluded historical paths.

Complete only when a recorded candidate tree hash has passed every ordered gate from an exact export, no dependency changed, and the real index remains empty.

### Task 16: 精确暂存、staged-tree 验证与 Release

**Files:**
- Stage: only the approved v0.39 production/tests/version/docs manifest from Tasks 1–14。
- Preserve unstaged: execution-start historical dirty list, including README/release metadata worktree content。

**Interfaces:**
- Consumes: Task 15 verified tree hash, explicit file manifest and HEAD-based index-only patches。
- Produces: one release commit `feat: add engineering memory layer` and annotated tag `v0.39.0`。

- [ ] **Step 1: Prepare the release RED guard**

Before staging, assert the real index is empty and record its tree:

```powershell
git diff --cached --quiet
git write-tree
```

If the index is non-empty, HEAD/baseline/tag/dirty changed, or the difference is not exactly the absence of approved v0.39 changes, stop without repair.

- [ ] **Step 2: Run RED and verify the expected failure**

Compare the empty-index tree to Task 15’s verified candidate tree with an equality assertion.

Expected: the assertion fails with `release tree is not staged`; an unexpected match means the index/baseline assumptions are wrong and release work stops.

- [ ] **Step 3: Implement the minimal precise staging behavior**

Reconfirm recorded historical dirty. Stage each clean v0.39 path explicitly. For README and `tests/release/test_release_metadata.py`, obtain blobs from execution-start HEAD, apply only approved v0.39 hunks in a temporary file, hash with `git hash-object -w`, and install with `git update-index --cacheinfo`; never stage their worktree files. Do not use broad pathspecs. Generate the staged Python manifest from `ACMR *.py` relative to baseline and verify excluded paths.

- [ ] **Step 4: Run GREEN and verify cached tree equality**

Run in order:

```powershell
git diff --cached --name-only
git diff --cached --check
git diff --cached
git write-tree
```

Expected: cached names exactly equal the approved manifest, diff contains only v0.39 hunks, check exits 0, and real tree hash exactly equals Task 15’s verified candidate tree. Any mismatch requires unstaging only the v0.39 entries with index plumbing, preserving worktree content, and stopping for review.

- [ ] **Step 5: Review, commit, tag and confirm completion**

Review the full cached diff once more, create `feat: add engineering memory layer`, and verify commit parent equals execution-start HEAD, commit tree equals the verified staged tree, commit file list equals the approved manifest, and index is empty. Then create `git tag -a v0.39.0 -m "Embedded Copilot v0.39.0"`; verify `git cat-file -t v0.39.0` is `tag`, dereferenced target is the new commit, and annotation is exact. Never push. Run `git status --short --untracked-files=all`, compare it with the recorded historical dirty list, and record commit hash, parent, tree, tag object type/target/message and every validation result.

Complete only when the one feature commit and annotated tag are verified, index is empty, historical dirty is preserved, and no failed gate is outstanding.

## Design Specification Coverage Matrix

| Design chapter | Implemented by Task(s) |
|---|---|
| 1. Summary | 5, 6, 11, 14 |
| 2. Goals | 1–12, 14 |
| 3. Explicit Non-goals | 13, 14, 15 |
| 4. Architecture | 5, 6, 11 |
| 5. Public Facade and Ports | 5 |
| 6. Aggregate and Revision Model | 6, 10, 12 |
| 7. Immutable Memory Record | 3, 6 |
| 8. Strongly Typed Payloads | 2 |
| 9. Trust State Model | 3, 8, 9, 10 |
| 10. Provenance | 2 |
| 11. Logical Key | 2, 6, 9 |
| 12. Replacement Semantics | 10 |
| 13. Verification Binding | 3, 8 |
| 14. Human Approval | 3, 9 |
| 15. State History | 3, 8, 9, 10 |
| 16. Public Commands | 4 |
| 17. Idempotency | 4, 6, 11 |
| 18. Permission | 5, 11 |
| 19. Audit | 11 |
| 20. InMemory Store | 6, 7, 10, 12 |
| 21. Query Model | 7 |
| 22. Public Results and Exceptions | 1, 4 |
| 23. Security Boundary | 13 |
| 24. Testing Strategy | 1–13, 15 |
| 25. Release and Quality Gate | 14–16 |
| 26. Git Isolation | 15, 16 |
| 27. Open Questions | locked contracts, Global Constraints, 6–11 |

## Plan Self-check

- [ ] 严格 UTF-8 解码成功且前三个字节不是 UTF-8 BOM。
- [ ] 恰好存在 16 个 `### Task N:` 标题，编号连续，每个 Task 均有 Files、Interfaces、RED、预期失败、最小实现、GREEN、diff review 和完成条件。
- [ ] 上表 27 章均至少映射到一个 Task。
- [ ] 12 个生产文件和 14 个测试文件均有单一职责且名称跨 Task 一致。
- [ ] 公共枚举、payload/provenance、record/evidence、commands/results、permission/audit、Protocol/facade/factory 按首次使用顺序定义。
- [ ] `EngineeringMemoryStorePort` 恰好八方法并保持原子领域命令边界。
- [ ] `MemoryAuthorizationRequest` 恰好九字段且无 payload、Finding、Verification/Approval 内容或 provenance。
- [ ] REVIEW_REQUIRED 明确追加 `CANDIDATE -> CANDIDATE`，record revision 和 aggregate revision 各增加一次。
- [ ] cursor 固定绑定 aggregate revision；Verification History 为 append-only identity。
- [ ] 延迟替代在同一个由锁保护的 Store 临界区完成双记录、projection、revision 和 receipt 更新。
- [ ] terminal audit replay 命中 receipt、复用 event key 且不重复 mutation。
- [ ] 不存在 hard delete、真实 persistence、Agent/LLM/RAG/Tool/Workspace mutation/filesystem/network/database/environment/hardware 能力。
- [ ] 只有一个最终功能提交和一个 annotated release tag，且不 push。
- [ ] 使用 strict UTF-8 Python reader 扫描禁止词；为避免把禁止词本身写入本文，扫描器通过片段拼接构造目标：`("TO"+"DO", "TB"+"D", "PLACE"+"HOLDER", "占位"+"符", "自行"+"实现", "类似"+"上一步", "appropriate error "+"handling", "write tests for "+"the above")`，任一命中即失败。

## Implementation Completion Record

未来实现完成时记录：动态 Python preflight 结果、每项 focused/regression/full gate、staged Python manifest、candidate/real tree hash equality、release commit/hash/parent/tree、annotated tag type/target/message、最终 index 与历史 dirty 状态。任何字段缺少可复核命令输出时，release 不成立。
