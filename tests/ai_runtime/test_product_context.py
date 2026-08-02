from __future__ import annotations

from embedded_copilot.ai_runtime import project_engineering_workspace
from embedded_copilot.product import create_product_runtime
from tests.product.conftest import artifact_report as artifact_report
from tests.product.conftest import feedback_sources as feedback_sources
from tests.product.conftest import firmware_request as firmware_request
from tests.product.conftest import generation_request as generation_request
from tests.product.conftest import make_request
from tests.product.conftest import product_sources as product_sources
from tests.product.conftest import validation_setup as validation_setup


def test_product_workspace_projects_only_safe_engineering_context(
    product_sources,
) -> None:
    workspace = create_product_runtime().product_workspace_port().create_project(
        make_request(product_sources)
    )
    before = workspace.model_dump(mode="json")

    context = project_engineering_workspace(workspace)

    assert context.project_id == workspace.project_id
    assert context.workspace_fingerprint == workspace.fingerprint
    assert context.current_stage == workspace.session.current_stage.value
    assert context.reference_ids == tuple(
        sorted(
            reference.reference_id
            for stage in workspace.stage_references
            for reference in stage.references
        )
    )
    assert context.decision_summaries == tuple(
        sorted({item.decision for item in workspace.decisions})
    )
    serialized = context.model_dump(mode="json")
    assert set(serialized).isdisjoint(
        {
            "stage_references",
            "timeline",
            "review_dashboard",
            "memory_records",
            "payload",
        }
    )
    assert workspace.model_dump(mode="json") == before
