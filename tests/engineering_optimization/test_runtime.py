from __future__ import annotations

import pytest

from embedded_copilot.engineering_artifacts import ArtifactType
from embedded_copilot.engineering_optimization import (
    EngineeringOptimizationRequest,
    EngineeringOptimizationRejected,
    OptimizationDomain,
    OptimizationFindingCode,
    OptimizationProposalState,
    create_engineering_optimization_runtime,
    engineering_optimization_request_fingerprint,
    optimization_target_fingerprint,
)
from tests.engineering_optimization.conftest import NOW, make_request, make_target


@pytest.mark.parametrize("domain", tuple(OptimizationDomain))
def test_explicit_domain_maps_to_deterministic_proposal_and_tradeoff(
    optimization_sources, domain
) -> None:
    contract, execution, validation, feedback = optimization_sources
    artifact_type = (
        ArtifactType.HARDWARE_MODEL
        if domain in {OptimizationDomain.POWER, OptimizationDomain.COST}
        else ArtifactType.FIRMWARE_STRUCTURE
    )
    target = make_target(contract, domain=domain, artifact_type=artifact_type)

    report = (
        create_engineering_optimization_runtime()
        .engineering_optimization_port()
        .analyze(
            make_request(
                contract,
                (target,),
                execution=execution,
                validation=validation,
                feedback=feedback,
            )
        )
    )

    proposal = report.proposals[0]
    assert proposal.optimization_id == target.optimization_id
    assert proposal.domain is domain
    assert proposal.target_artifact_fingerprint == target.target_artifact_fingerprint
    assert proposal.state is OptimizationProposalState.REVIEW_REQUIRED
    assert proposal.review_required is True
    assert proposal.tradeoffs
    assert (
        report.change_proposals[0].optimization_proposal_fingerprint
        == proposal.fingerprint
    )
    assert (
        report.revision_plans[0].optimization_proposal_fingerprint
        == proposal.fingerprint
    )
    assert (
        report.validation_plans[0].optimization_proposal_fingerprint
        == proposal.fingerprint
    )
    assert report.candidate_semantics == "unverified"
    assert report.review_required is True


def test_source_signals_are_projected_without_mutating_inputs(
    optimization_sources,
) -> None:
    contract, execution, validation, feedback = optimization_sources
    request = make_request(
        contract,
        (make_target(contract),),
        execution=execution,
        validation=validation,
        feedback=feedback,
    )
    before = request.model_dump(mode="json")

    report = (
        create_engineering_optimization_runtime()
        .engineering_optimization_port()
        .analyze(request)
    )

    assert (
        OptimizationFindingCode.EXECUTION_ISSUE_DETECTED in report.review.finding_codes
    )
    assert (
        OptimizationFindingCode.FEEDBACK_CHANGE_REQUESTED in report.review.finding_codes
    )
    assert (
        OptimizationFindingCode.OPTIMIZATION_REVIEW_REQUIRED
        in report.review.finding_codes
    )
    assert report.review.execution_report_fingerprint == execution.fingerprint
    assert report.review.validation_report_fingerprint == validation.fingerprint
    assert report.review.feedback_report_fingerprint == feedback.fingerprint
    assert request.model_dump(mode="json") == before


def test_no_source_issue_returns_reviewable_empty_analysis(
    optimization_sources,
) -> None:
    contract, _, _, _ = optimization_sources
    report = (
        create_engineering_optimization_runtime()
        .engineering_optimization_port()
        .analyze(make_request(contract, (make_target(contract),)))
    )
    assert report.proposals == ()
    assert report.change_proposals == ()
    assert report.revision_plans == ()
    assert report.validation_plans == ()
    assert report.review.finding_codes == (
        OptimizationFindingCode.SOURCE_SIGNAL_REQUIRED,
    )


def test_cross_artifact_target_is_rejected(optimization_sources) -> None:
    contract, _, _, _ = optimization_sources
    target_values = {
        **make_target(contract).model_dump(mode="python"),
        "target_artifact_fingerprint": "sha256:" + "0" * 64,
    }
    target_values.pop("fingerprint")
    target_type = type(make_target(contract))
    target = target_type(
        **target_values,
        fingerprint=optimization_target_fingerprint(**target_values),
    )
    request_values = dict(
        request_id="optimization-request-1",
        artifact_contract=contract,
        execution_report=None,
        validation_report=None,
        feedback_report=None,
        optimization_targets=(target,),
        requested_at=NOW,
    )
    request = EngineeringOptimizationRequest(
        **request_values,
        fingerprint=engineering_optimization_request_fingerprint(**request_values),
    )
    with pytest.raises(
        EngineeringOptimizationRejected, match="optimization request is invalid"
    ):
        create_engineering_optimization_runtime().engineering_optimization_port().analyze(
            request
        )


def test_report_serialization_contains_no_upstream_runtime_or_sensitive_body(
    optimization_sources,
) -> None:
    contract, execution, validation, feedback = optimization_sources
    report = (
        create_engineering_optimization_runtime()
        .engineering_optimization_port()
        .analyze(
            make_request(
                contract,
                (make_target(contract),),
                execution=execution,
                validation=validation,
                feedback=feedback,
            )
        )
    )
    payload = report.model_dump(mode="json")
    forbidden = {
        "artifact_contract",
        "execution_report",
        "validation_report",
        "feedback_report",
        "payload",
        "stdout",
        "stderr",
        "command",
        "path",
        "provider",
    }

    def keys(value):
        if isinstance(value, dict):
            yield from value
            for nested in value.values():
                yield from keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from keys(nested)

    assert forbidden.isdisjoint(set(keys(payload)))
