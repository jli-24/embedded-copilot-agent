from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_artifacts import ArtifactType
from embedded_copilot.engineering_feedback import create_engineering_feedback_runtime
from embedded_copilot.engineering_optimization import (
    EngineeringOptimizationRequest,
    EngineeringOptimizationTarget,
    OptimizationDomain,
    engineering_optimization_request_fingerprint,
    optimization_target_fingerprint,
)
from tests.engineering_feedback import conftest as _feedback_fixtures
from tests.engineering_feedback.test_contracts import (
    make_request as make_feedback_request,
)

artifact_report = _feedback_fixtures.artifact_report
feedback_sources = _feedback_fixtures.feedback_sources
firmware_request = _feedback_fixtures.firmware_request
generation_request = _feedback_fixtures.generation_request
validation_setup = _feedback_fixtures.validation_setup

NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)


def artifact_fingerprint(contract, artifact_type=ArtifactType.FIRMWARE_STRUCTURE):
    return next(
        item.artifact_fingerprint
        for item in contract.artifacts
        if item.artifact_type is artifact_type
    )


def make_target(
    contract,
    *,
    optimization_id="optimization-1",
    domain=OptimizationDomain.PERFORMANCE,
    artifact_type=ArtifactType.FIRMWARE_STRUCTURE,
    problem_reference="EXECUTION_RESULT",
    current_state="REVIEW_REQUIRED",
    desired_state="IMPROVED",
):
    values = dict(
        optimization_id=optimization_id,
        target_artifact_fingerprint=artifact_fingerprint(contract, artifact_type),
        domain=domain,
        problem_reference=problem_reference,
        current_state=current_state,
        desired_state=desired_state,
    )
    return EngineeringOptimizationTarget(
        **values,
        fingerprint=optimization_target_fingerprint(**values),
    )


def make_request(
    contract,
    targets,
    *,
    execution=None,
    validation=None,
    feedback=None,
):
    values = dict(
        request_id="optimization-request-1",
        artifact_contract=contract,
        execution_report=execution,
        validation_report=validation,
        feedback_report=feedback,
        optimization_targets=targets,
        requested_at=NOW,
    )
    return EngineeringOptimizationRequest(
        **values,
        fingerprint=engineering_optimization_request_fingerprint(**values),
    )


@pytest.fixture
def optimization_sources(feedback_sources):
    contract, execution, validation = feedback_sources
    target = artifact_fingerprint(contract)
    item = _feedback_fixtures.make_change_item(target)
    feedback = (
        create_engineering_feedback_runtime()
        .engineering_feedback_port()
        .submit_feedback(
            make_feedback_request(
                contract,
                (item,),
                execution=execution,
                validation=validation,
            )
        )
    )
    return contract, execution, validation, feedback
