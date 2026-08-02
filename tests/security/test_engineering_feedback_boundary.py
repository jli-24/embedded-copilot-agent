from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot" / "engineering_feedback"


def _modules():
    return tuple(sorted(ROOT.rglob("*.py")))


def test_feedback_package_has_no_execution_or_mutation_capability() -> None:
    forbidden_imports = {
        "os",
        "pathlib",
        "subprocess",
        "socket",
        "sqlite3",
        "requests",
        "httpx",
        "serial",
        "git",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "embedded_copilot.engineering_generation",
    }
    forbidden_calls = {
        "modify_artifact",
        "apply_change",
        "auto_patch",
        "auto_execute",
        "build",
        "flash",
        "debug",
        "execute",
        "open",
        "write_text",
        "write_bytes",
    }
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not any(alias.name.startswith(name) for name in forbidden_imports)
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module.startswith(name) for name in forbidden_imports
                )
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                assert name not in forbidden_calls


def test_only_typed_integration_imports_upstream_public_contracts() -> None:
    upstream = (
        "embedded_copilot.engineering_artifacts",
        "embedded_copilot.engineering_execution",
        "embedded_copilot.engineering_validation",
    )
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        if any(
            any(name.startswith(prefix) for prefix in upstream) for name in imported
        ):
            assert path.as_posix().endswith("integration/inputs.py")


def test_public_exports_do_not_expose_internal_handlers() -> None:
    import embedded_copilot.engineering_feedback as package

    assert package.__all__
    assert not {
        "_EngineeringFeedbackService",
        "project_feedback",
        "project_request",
    }.intersection(package.__all__)
    assert all(
        "Port" not in name or name == "EngineeringFeedbackPort"
        for name in package.__all__
    )


def test_serialized_report_contains_only_safe_projection() -> None:
    from datetime import UTC, datetime

    from embedded_copilot.engineering_feedback import (
        EngineeringFeedbackProjection,
        EngineeringFeedbackReport,
        EngineeringFeedbackReviewProjection,
        FeedbackFindingCode,
        FeedbackItemType,
        FeedbackReviewOutcome,
        engineering_feedback_projection_fingerprint,
        engineering_feedback_report_fingerprint,
        engineering_feedback_review_fingerprint,
    )
    from tests.engineering_feedback.conftest import make_simple_item

    target = "sha256:" + "1" * 64
    item = make_simple_item(FeedbackItemType.COMMENT, target)
    projection_values = dict(
        feedback_id="feedback-1",
        artifact_contract_fingerprint="sha256:" + "2" * 64,
        artifact_source_fingerprint="sha256:" + "3" * 64,
        execution_report_fingerprint="sha256:" + "4" * 64,
        validation_report_fingerprint="sha256:" + "5" * 64,
        items=(item,),
        submitted_at=datetime(2026, 8, 9, tzinfo=UTC),
    )
    projection = EngineeringFeedbackProjection(
        **projection_values,
        fingerprint=engineering_feedback_projection_fingerprint(**projection_values),
    )
    review_values = dict(
        feedback_id="feedback-1",
        outcome=FeedbackReviewOutcome.COMMENT_RECORDED,
        item_count=1,
        change_request_count=0,
        revision_proposal_count=0,
        execution_report_fingerprint="sha256:" + "4" * 64,
        validation_report_fingerprint="sha256:" + "5" * 64,
        finding_codes=(FeedbackFindingCode.COMMENT_RECORDED,),
        review_required=True,
    )
    review = EngineeringFeedbackReviewProjection(
        **review_values,
        fingerprint=engineering_feedback_review_fingerprint(**review_values),
    )
    report_values = dict(
        feedback=projection,
        change_requests=(),
        revision_proposals=(),
        review=review,
        candidate_semantics="unverified",
        review_required=True,
    )
    report = EngineeringFeedbackReport(
        **report_values,
        fingerprint=engineering_feedback_report_fingerprint(**report_values),
    )
    serialized = report.model_dump_json().casefold()
    for forbidden in (
        "execution_contract",
        "evidence_trace",
        "test_plan",
        "buildport",
        "flashport",
        "debugport",
        "stdout",
        "stderr",
        "path",
        "payload",
    ):
        assert forbidden not in serialized
