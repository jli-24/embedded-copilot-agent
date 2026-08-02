from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_feedback import create_engineering_feedback_runtime
from embedded_copilot.engineering_optimization import (
    OptimizationDomain,
    create_engineering_optimization_runtime,
)
from embedded_copilot.product import (
    CreateProjectRequest,
    ProductDecisionOutcome,
    ProductDecisionProjection,
    create_project_request_fingerprint,
    product_decision_fingerprint,
)
from tests.engineering_feedback import conftest as _feedback_fixtures
from tests.engineering_feedback.test_contracts import (
    make_request as make_feedback_request,
)
from tests.engineering_optimization.conftest import (
    make_request as make_optimization_request,
)
from tests.engineering_optimization.conftest import make_target

artifact_report = _feedback_fixtures.artifact_report
feedback_sources = _feedback_fixtures.feedback_sources
firmware_request = _feedback_fixtures.firmware_request
generation_request = _feedback_fixtures.generation_request
validation_setup = _feedback_fixtures.validation_setup

NOW = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)


def make_decision() -> ProductDecisionProjection:
    values = dict(
        decision_id="decision-1",
        decision="USE_ESP32_S3",
        reason="CAMERA_AND_WIFI_REQUIREMENT",
        evidence_references=("evidence-mcu",),
        feedback_references=("feedback-1",),
        outcome=ProductDecisionOutcome.ACCEPTED,
    )
    return ProductDecisionProjection(
        **values,
        fingerprint=product_decision_fingerprint(**values),
    )


@pytest.fixture
def product_sources(generation_request, feedback_sources):
    contract, execution, validation = feedback_sources
    target = next(
        item.artifact_fingerprint
        for item in contract.artifacts
        if item.artifact_type.value == "FIRMWARE_STRUCTURE"
    )
    change_item = _feedback_fixtures.make_change_item(target)
    feedback = (
        create_engineering_feedback_runtime()
        .engineering_feedback_port()
        .submit_feedback(
            make_feedback_request(
                contract,
                (change_item,),
                execution=execution,
                validation=validation,
            )
        )
    )
    optimization = (
        create_engineering_optimization_runtime()
        .engineering_optimization_port()
        .analyze(
            make_optimization_request(
                contract,
                (
                    make_target(
                        contract,
                        domain=OptimizationDomain.PERFORMANCE,
                    ),
                ),
                execution=execution,
                validation=validation,
                feedback=feedback,
            )
        )
    )
    return dict(
        requirement=generation_request.requirement,
        plan=None,
        context=generation_request.context,
        hardware_proposal=generation_request.hardware_proposal,
        firmware_proposal=generation_request.firmware_proposal,
        validation_report=validation,
        artifact_contract=contract,
        execution_report=execution,
        feedback_report=feedback,
        optimization_report=optimization,
    )


def make_request(sources, **updates) -> CreateProjectRequest:
    values = dict(
        project_id="project-1",
        project_name="ESP32-S3 Smart Camera",
        project_summary="Reviewable embedded camera engineering project.",
        session_id="session-product-1",
        decisions=(make_decision(),),
        created_at=NOW,
        **sources,
    )
    values.update(updates)
    return CreateProjectRequest(
        **values,
        fingerprint=create_project_request_fingerprint(**values),
    )
