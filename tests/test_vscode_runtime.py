from __future__ import annotations

import importlib.util
import inspect
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

import embedded_copilot.vscode_runtime as public_runtime
from embedded_copilot.coding_runtime import (
    BuildAnalysisRequest,
    CodeFileInput,
    DiffReviewRequest,
    ProjectAnalysisRequest,
    create_coding_runtime,
)
from embedded_copilot.workspace_runtime import (
    ApprovalContext,
    ApprovalStatus,
    ChangeProposal,
    WorkspaceInspectionRequest,
    create_workspace_runtime,
)

CONTEXT_ID = "context:0123456789abcdef01234567"


def test_vscode_runtime_package_exists() -> None:
    assert importlib.util.find_spec("embedded_copilot.vscode_runtime") is not None


def test_public_contract_is_narrow_and_capabilities_are_deterministic() -> None:
    assert set(public_runtime.__all__) == {
        "ChangeProposalResult",
        "DEFAULT_CAPABILITIES",
        "MCPToolAdapter",
        "MCPToolName",
        "MCPToolResult",
        "VSCodeCapability",
        "VSCodeCapabilityUnavailable",
        "VSCodePort",
        "VSCodeRuntime",
        "create_vscode_runtime",
    }
    assert tuple(public_runtime.VSCodeCapability) == (
        public_runtime.VSCodeCapability.READ_CONTEXT,
        public_runtime.VSCodeCapability.ANALYZE_CODE,
        public_runtime.VSCodeCapability.ANALYZE_BUILD,
        public_runtime.VSCodeCapability.REVIEW_DIFF,
        public_runtime.VSCodeCapability.CREATE_PROPOSAL,
        public_runtime.VSCodeCapability.APPLY_APPROVED_CHANGE,
    )
    assert (
        public_runtime.DEFAULT_CAPABILITIES
        == tuple(public_runtime.VSCodeCapability)[:-1]
    )
    assert {
        name
        for name, value in public_runtime.VSCodeRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"vscode_port"}
    assert tuple(
        inspect.signature(public_runtime.VSCodeRuntime.vscode_port).parameters
    ) == ("self",)
    assert tuple(
        inspect.signature(public_runtime.create_vscode_runtime).parameters
    ) == ("coding_port", "workspace_port", "enabled_capabilities")
    assert {
        name
        for name, value in public_runtime.VSCodePort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {
        "inspect_context",
        "analyze_code",
        "analyze_build",
        "review_diff",
        "create_change_proposal",
        "apply_approved_change",
    }


def test_mcp_result_is_frozen_extra_forbid_and_canonical() -> None:
    result = public_runtime.MCPToolResult(
        tool_name=public_runtime.MCPToolName.ANALYZE_CODE,
        is_error=False,
        payload_json='{"answer":1}',
    )

    assert result.payload_json == '{"answer":1}'
    with pytest.raises(ValidationError):
        result.payload_json = "{}"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        public_runtime.MCPToolResult(
            tool_name=public_runtime.MCPToolName.ANALYZE_CODE,
            is_error=False,
            payload_json='{"answer": 1}',
        )
    with pytest.raises(ValidationError):
        public_runtime.MCPToolResult(
            tool_name=public_runtime.MCPToolName.ANALYZE_CODE,
            is_error=False,
            payload_json='{"answer":NaN}',
        )
    with pytest.raises(ValidationError):
        public_runtime.MCPToolResult.model_validate(
            {
                "tool_name": "analyze_code",
                "is_error": False,
                "payload_json": "{}",
                "unexpected": True,
            }
        )


def test_mcp_result_enforces_success_and_error_payload_boundary() -> None:
    error = public_runtime.MCPToolResult(
        tool_name=public_runtime.MCPToolName.ANALYZE_CODE,
        is_error=True,
        error_code="invalid_arguments",
    )

    assert error.payload_json is None
    with pytest.raises(ValidationError):
        public_runtime.MCPToolResult(
            tool_name=public_runtime.MCPToolName.ANALYZE_CODE,
            is_error=True,
            payload_json="{}",
            error_code="invalid_arguments",
        )
    with pytest.raises(ValidationError):
        public_runtime.MCPToolResult(
            tool_name=public_runtime.MCPToolName.ANALYZE_CODE,
            is_error=False,
            error_code="invalid_arguments",
        )
    unknown = public_runtime.MCPToolResult(
        tool_name=None,
        is_error=True,
        error_code="unknown_tool",
    )
    assert unknown.tool_name is None


def _runtime(
    tmp_path: Path,
    *,
    capabilities: tuple[object, ...] | None = None,
) -> public_runtime.VSCodeRuntime:
    kwargs: dict[str, object] = {}
    if capabilities is not None:
        kwargs["enabled_capabilities"] = capabilities
    return public_runtime.create_vscode_runtime(
        coding_port=create_coding_runtime().coding_port(),
        workspace_port=create_workspace_runtime(tmp_path).workspace_port(),
        **kwargs,
    )


def _proposal(snapshot_fingerprint: str) -> ChangeProposal:
    return ChangeProposal(
        proposal_id="proposal:v034",
        workspace_snapshot_id=snapshot_fingerprint,
        target_files=("src/main.py",),
        diff=(
            "diff --git a/src/main.py b/src/main.py\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1 +1 @@\n"
            "-value = 1\n"
            "+value = 2\n"
        ),
        reason="Apply an engineer-reviewed value change.",
        created_by="engineer:1",
    )


def _approval(proposal: ChangeProposal, *, status: ApprovalStatus) -> ApprovalContext:
    return ApprovalContext(
        proposal_id=proposal.proposal_id,
        workspace_id="workspace:1",
        workspace_snapshot_id=proposal.workspace_snapshot_id,
        target_files=proposal.target_files,
        status=status,
        approved_by="engineer:1",
        approved_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )


def test_read_only_operations_delegate_to_existing_runtime_ports(
    tmp_path: Path,
) -> None:
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    port = _runtime(tmp_path).vscode_port()

    workspace = port.inspect_context(
        WorkspaceInspectionRequest(
            workspace_id="workspace:1",
            relative_paths=("src/main.py",),
        )
    )
    code = port.analyze_code(
        ProjectAnalysisRequest(
            context_id=CONTEXT_ID,
            files=(CodeFileInput(path="src/main.py", content="value = 1\n"),),
        )
    )
    build = port.analyze_build(
        BuildAnalysisRequest(
            compiler="GCC",
            log="src/main.py:1:1: error: invalid syntax\n",
        )
    )
    review = port.review_diff(
        DiffReviewRequest(diff=_proposal(workspace.snapshot_fingerprint).diff)
    )

    assert workspace.files[0].relative_path == "src/main.py"
    assert code.snapshot.files[0].content_sha256
    assert build.issues[0].error_type == "COMPILER_ERROR"
    assert review.candidate_semantics == "unverified"


def test_create_proposal_validates_and_default_runtime_denies_apply(
    tmp_path: Path,
) -> None:
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    port = _runtime(tmp_path).vscode_port()
    snapshot = port.inspect_context(
        WorkspaceInspectionRequest(
            workspace_id="workspace:1",
            relative_paths=("src/main.py",),
        )
    )
    proposal = _proposal(snapshot.snapshot_fingerprint)

    created = port.create_change_proposal(proposal)

    assert created.proposal == proposal
    assert created.validation.status == "WAITING_APPROVAL"
    with pytest.raises(public_runtime.VSCodeCapabilityUnavailable):
        port.apply_approved_change(
            proposal,
            _approval(proposal, status=ApprovalStatus.APPROVED),
        )
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_explicit_apply_capability_still_uses_workspace_approval(
    tmp_path: Path,
) -> None:
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    capabilities = (
        *public_runtime.DEFAULT_CAPABILITIES,
        public_runtime.VSCodeCapability.APPLY_APPROVED_CHANGE,
    )
    port = _runtime(tmp_path, capabilities=capabilities).vscode_port()
    snapshot = port.inspect_context(
        WorkspaceInspectionRequest(
            workspace_id="workspace:1",
            relative_paths=("src/main.py",),
        )
    )
    proposal = _proposal(snapshot.snapshot_fingerprint)
    port.create_change_proposal(proposal)

    waiting = port.apply_approved_change(
        proposal,
        _approval(proposal, status=ApprovalStatus.WAITING_APPROVAL),
    )
    applied = port.apply_approved_change(
        proposal,
        _approval(proposal, status=ApprovalStatus.APPROVED),
    )

    assert waiting.status == "REJECTED"
    assert waiting.error_code == "approval_required"
    assert applied.status == "APPLIED"
    assert applied.audit_event is not None
    assert "value =" not in applied.audit_event.model_dump_json()
    assert target.read_text(encoding="utf-8") == "value = 2\n"


def test_factory_rejects_duplicate_or_non_tuple_capabilities(tmp_path: Path) -> None:
    coding_port = create_coding_runtime().coding_port()
    workspace_port = create_workspace_runtime(tmp_path).workspace_port()

    with pytest.raises(ValueError, match="capabilities"):
        public_runtime.create_vscode_runtime(
            coding_port=coding_port,
            workspace_port=workspace_port,
            enabled_capabilities=(
                public_runtime.VSCodeCapability.READ_CONTEXT,
                public_runtime.VSCodeCapability.READ_CONTEXT,
            ),
        )
    with pytest.raises(TypeError, match="capabilities"):
        public_runtime.create_vscode_runtime(
            coding_port=coding_port,
            workspace_port=workspace_port,
            enabled_capabilities=[  # type: ignore[arg-type]
                public_runtime.VSCodeCapability.READ_CONTEXT
            ],
        )


def test_mcp_adapter_registers_fixed_tools_and_apply_is_opt_in(tmp_path: Path) -> None:
    from embedded_copilot.vscode_runtime.mcp_server import _build_mcp_adapter

    port = _runtime(tmp_path).vscode_port()
    default_adapter = _build_mcp_adapter(port)
    all_capabilities = tuple(public_runtime.VSCodeCapability)
    write_adapter = _build_mcp_adapter(
        _runtime(tmp_path, capabilities=all_capabilities).vscode_port(),
        enabled_capabilities=all_capabilities,
    )

    assert default_adapter.list_tools() == (
        public_runtime.MCPToolName.INSPECT_WORKSPACE_CONTEXT,
        public_runtime.MCPToolName.ANALYZE_CODE,
        public_runtime.MCPToolName.ANALYZE_BUILD_LOG,
        public_runtime.MCPToolName.REVIEW_DIFF,
        public_runtime.MCPToolName.CREATE_CHANGE_PROPOSAL,
    )
    assert write_adapter.list_tools() == tuple(public_runtime.MCPToolName)


def test_mcp_adapter_converts_arguments_and_validates_proposal(
    tmp_path: Path,
) -> None:
    from embedded_copilot.vscode_runtime.mcp_server import _build_mcp_adapter

    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    adapter = _build_mcp_adapter(_runtime(tmp_path).vscode_port())

    workspace_result = adapter.call_tool(
        "inspect_workspace_context",
        {
            "workspace_id": "workspace:1",
            "relative_paths": ["src/main.py"],
        },
    )
    workspace_payload = json.loads(workspace_result.payload_json or "")
    analyze_result = adapter.call_tool(
        "analyze_code",
        {
            "context_id": CONTEXT_ID,
            "files": [{"path": "src/main.py", "content": "value = 1\n"}],
        },
    )
    build_result = adapter.call_tool(
        "analyze_build_log",
        {
            "compiler": "GCC",
            "log": "src/main.py:1:1: error: invalid syntax\n",
        },
    )
    review_result = adapter.call_tool(
        "review_diff",
        {
            "diff": _proposal(workspace_payload["snapshot_fingerprint"]).diff,
        },
    )
    proposal = _proposal(workspace_payload["snapshot_fingerprint"])
    proposal_result = adapter.call_tool(
        "create_change_proposal",
        proposal.model_dump(mode="json"),
    )
    proposal_payload = json.loads(proposal_result.payload_json or "")

    assert not workspace_result.is_error
    assert not analyze_result.is_error
    assert not build_result.is_error
    assert not review_result.is_error
    assert proposal_payload["validation"]["status"] == "WAITING_APPROVAL"
    for result in (
        workspace_result,
        analyze_result,
        build_result,
        review_result,
        proposal_result,
    ):
        assert result.payload_json == json.dumps(
            json.loads(result.payload_json or ""),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def test_mcp_adapter_returns_sanitized_boundary_errors(tmp_path: Path) -> None:
    from embedded_copilot.vscode_runtime.mcp_server import _build_mcp_adapter

    adapter = _build_mcp_adapter(_runtime(tmp_path).vscode_port())

    invalid = adapter.call_tool(
        "analyze_code",
        {
            "context_id": CONTEXT_ID,
            "files": [{"path": "src/main.py", "content": "value = 1\n"}],
            "path": "C:\\private\\main.py",
        },
    )
    denied = adapter.call_tool(
        "apply_approved_change",
        {},
    )
    unknown = adapter.call_tool("write_file", {"path": "C:\\private\\main.py"})

    assert (invalid.is_error, invalid.error_code) == (True, "invalid_arguments")
    assert (denied.is_error, denied.error_code) == (True, "capability_denied")
    assert (unknown.is_error, unknown.error_code, unknown.tool_name) == (
        True,
        "unknown_tool",
        None,
    )
    serialized = (
        invalid.model_dump_json() + denied.model_dump_json() + unknown.model_dump_json()
    )
    assert "C:\\private" not in serialized
    assert "traceback" not in serialized.casefold()


def test_mcp_adapter_applies_only_through_approved_workspace_change(
    tmp_path: Path,
) -> None:
    from embedded_copilot.vscode_runtime.mcp_server import _build_mcp_adapter

    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    capabilities = tuple(public_runtime.VSCodeCapability)
    adapter = _build_mcp_adapter(
        _runtime(tmp_path, capabilities=capabilities).vscode_port(),
        enabled_capabilities=capabilities,
    )
    snapshot_result = adapter.call_tool(
        "inspect_workspace_context",
        {
            "workspace_id": "workspace:1",
            "relative_paths": ["src/main.py"],
        },
    )
    snapshot = json.loads(snapshot_result.payload_json or "")
    proposal = _proposal(snapshot["snapshot_fingerprint"])
    adapter.call_tool(
        "create_change_proposal",
        proposal.model_dump(mode="json"),
    )

    result = adapter.call_tool(
        "apply_approved_change",
        {
            "proposal": proposal.model_dump(mode="json"),
            "approval": _approval(
                proposal,
                status=ApprovalStatus.APPROVED,
            ).model_dump(mode="json"),
        },
    )

    payload = json.loads(result.payload_json or "")
    assert payload["status"] == "APPLIED"
    assert "value =" not in json.dumps(payload)
    assert target.read_text(encoding="utf-8") == "value = 2\n"


class _FailingVSCodePort:
    def inspect_context(self, request: object) -> object:
        raise RuntimeError("C:\\private\\workspace\\secret.py")

    def analyze_code(self, request: object) -> object:
        raise RuntimeError("C:\\private\\workspace\\secret.py")

    def analyze_build(self, request: object) -> object:
        raise RuntimeError("C:\\private\\workspace\\secret.py")

    def review_diff(self, request: object) -> object:
        raise RuntimeError("C:\\private\\workspace\\secret.py")

    def create_change_proposal(self, proposal: object) -> object:
        raise RuntimeError("C:\\private\\workspace\\secret.py")

    def apply_approved_change(self, proposal: object, approval: object) -> object:
        raise RuntimeError("C:\\private\\workspace\\secret.py")


class _NonFiniteOutput(BaseModel):
    latency_ms: float


class _NonFiniteVSCodePort(_FailingVSCodePort):
    def analyze_code(self, request: object) -> object:
        return _NonFiniteOutput(latency_ms=float("nan"))


def test_mcp_adapter_does_not_leak_runtime_exception_text() -> None:
    from embedded_copilot.vscode_runtime.mcp_server import _build_mcp_adapter

    adapter = _build_mcp_adapter(_FailingVSCodePort())  # type: ignore[arg-type]

    result = adapter.call_tool(
        "analyze_code",
        {
            "context_id": CONTEXT_ID,
            "files": [{"path": "src/main.py", "content": "value = 1\n"}],
        },
    )

    assert (result.is_error, result.error_code) == (True, "runtime_unavailable")
    assert "private" not in result.model_dump_json().casefold()


def test_mcp_adapter_maps_nonstandard_json_output_to_safe_error() -> None:
    from embedded_copilot.vscode_runtime.mcp_server import _build_mcp_adapter

    adapter = _build_mcp_adapter(_NonFiniteVSCodePort())  # type: ignore[arg-type]

    result = adapter.call_tool(
        "analyze_code",
        {
            "context_id": CONTEXT_ID,
            "files": [{"path": "src/main.py", "content": "value = 1\n"}],
        },
    )

    assert (result.is_error, result.error_code) == (True, "runtime_unavailable")
