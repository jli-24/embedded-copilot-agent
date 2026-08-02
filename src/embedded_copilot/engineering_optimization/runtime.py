"""Deterministic, proposal-only engineering optimization analysis."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.engineering_optimization.contracts import (
    EngineeringOptimizationPort,
)
from embedded_copilot.engineering_optimization.exceptions import (
    EngineeringOptimizationRejected,
)
from embedded_copilot.engineering_optimization.integration.inputs import (
    EngineeringOptimizationRequest,
    _ProjectedOptimizationRequest,
    project_request,
)
from embedded_copilot.engineering_optimization.models import (
    EngineeringOptimizationProposal,
    EngineeringOptimizationReport,
    EngineeringOptimizationReviewProjection,
    EngineeringOptimizationTarget,
    EngineeringTradeoffProjection,
    OptimizationChangeProposal,
    OptimizationDomain,
    OptimizationFindingCode,
    OptimizationProposalState,
    OptimizationRevisionPlan,
    OptimizationReviewState,
    OptimizationValidationPlan,
    engineering_optimization_proposal_fingerprint,
    engineering_optimization_report_fingerprint,
    engineering_optimization_review_fingerprint,
    engineering_tradeoff_fingerprint,
    optimization_change_proposal_fingerprint,
    optimization_revision_plan_fingerprint,
    optimization_validation_plan_fingerprint,
)

_DOMAIN_CODES = {
    OptimizationDomain.POWER: (
        "REDUCE_ACTIVE_POWER",
        "LOWER_POWER_USAGE",
        "POWER_TRADEOFF_REVIEW",
        "POWER_VALIDATION_REQUIRED",
    ),
    OptimizationDomain.PERFORMANCE: (
        "IMPROVE_PIPELINE_EFFICIENCY",
        "HIGHER_THROUGHPUT",
        "PERFORMANCE_TRADEOFF_REVIEW",
        "PERFORMANCE_VALIDATION_REQUIRED",
    ),
    OptimizationDomain.MEMORY: (
        "REDUCE_MEMORY_PRESSURE",
        "LOWER_MEMORY_USAGE",
        "MEMORY_TRADEOFF_REVIEW",
        "MEMORY_VALIDATION_REQUIRED",
    ),
    OptimizationDomain.COST: (
        "REVIEW_COMPONENT_COST",
        "LOWER_COMPONENT_COST",
        "COST_TRADEOFF_REVIEW",
        "COST_VALIDATION_REQUIRED",
    ),
    OptimizationDomain.RELIABILITY: (
        "IMPROVE_FAILURE_RESILIENCE",
        "HIGHER_SYSTEM_RELIABILITY",
        "RELIABILITY_TRADEOFF_REVIEW",
        "RELIABILITY_VALIDATION_REQUIRED",
    ),
}


class _EngineeringOptimizationService(EngineeringOptimizationPort):
    __slots__ = ()

    def analyze(
        self,
        request: EngineeringOptimizationRequest,
    ) -> EngineeringOptimizationReport:
        try:
            projected = project_request(request)
            safe = projected.request
            findings = _source_findings(projected)
            proposals = ()
            changes = ()
            revisions = ()
            validations = ()
            if findings:
                proposals = tuple(_proposal(item) for item in safe.optimization_targets)
                changes = tuple(
                    _change(item, proposal)
                    for item, proposal in zip(
                        safe.optimization_targets, proposals, strict=True
                    )
                )
                revisions = tuple(
                    _revision(item, proposal)
                    for item, proposal in zip(
                        safe.optimization_targets, proposals, strict=True
                    )
                )
                validations = tuple(
                    _validation(item, proposal)
                    for item, proposal in zip(
                        safe.optimization_targets, proposals, strict=True
                    )
                )
                findings.update(
                    {
                        OptimizationFindingCode.OPTIMIZATION_REVIEW_REQUIRED,
                        OptimizationFindingCode.REVALIDATION_REQUIRED,
                    }
                )
            else:
                findings.add(OptimizationFindingCode.SOURCE_SIGNAL_REQUIRED)
            ordered_findings = _ordered_findings(findings)
            review_values = dict(
                request_id=safe.request_id,
                artifact_contract_fingerprint=safe.artifact_contract.fingerprint,
                execution_report_fingerprint=projected.execution_report_fingerprint,
                validation_report_fingerprint=projected.validation_report_fingerprint,
                feedback_report_fingerprint=projected.feedback_report_fingerprint,
                proposal_count=len(proposals),
                change_proposal_count=len(changes),
                revision_plan_count=len(revisions),
                validation_plan_count=len(validations),
                finding_codes=ordered_findings,
                state=OptimizationReviewState.PENDING,
                review_required=True,
            )
            review = EngineeringOptimizationReviewProjection(
                **review_values,
                fingerprint=engineering_optimization_review_fingerprint(
                    **review_values
                ),
            )
            report_values = dict(
                request_id=safe.request_id,
                artifact_contract_fingerprint=safe.artifact_contract.fingerprint,
                artifact_source_fingerprint=(
                    safe.artifact_contract.artifact_source_fingerprint
                ),
                proposals=proposals,
                change_proposals=changes,
                revision_plans=revisions,
                validation_plans=validations,
                review=review,
                requested_at=safe.requested_at,
                candidate_semantics="unverified",
                review_required=True,
            )
            return EngineeringOptimizationReport(
                **report_values,
                fingerprint=engineering_optimization_report_fingerprint(
                    **report_values
                ),
            )
        except EngineeringOptimizationRejected:
            raise
        except (TypeError, ValueError, ValidationError):
            raise EngineeringOptimizationRejected(
                "optimization request is invalid"
            ) from None


def _source_findings(
    request: _ProjectedOptimizationRequest,
) -> set[OptimizationFindingCode]:
    findings: set[OptimizationFindingCode] = set()
    if request.validation_issue:
        findings.add(OptimizationFindingCode.VALIDATION_ISSUE_DETECTED)
    if request.execution_issue:
        findings.add(OptimizationFindingCode.EXECUTION_ISSUE_DETECTED)
    if request.feedback_change_requested:
        findings.add(OptimizationFindingCode.FEEDBACK_CHANGE_REQUESTED)
    return findings


def _proposal(target: EngineeringOptimizationTarget) -> EngineeringOptimizationProposal:
    proposal_code, benefit_code, risk_code, _ = _DOMAIN_CODES[target.domain]
    tradeoff_values = dict(
        option=proposal_code,
        benefit=benefit_code,
        risk=risk_code,
        cost="ENGINEERING_CHANGE_COST_UNKNOWN",
        confidence=0.5,
    )
    tradeoff = EngineeringTradeoffProjection(
        **tradeoff_values,
        fingerprint=engineering_tradeoff_fingerprint(**tradeoff_values),
    )
    values = dict(
        optimization_id=target.optimization_id,
        target_artifact_fingerprint=target.target_artifact_fingerprint,
        domain=target.domain,
        problem_reference=target.problem_reference,
        current_state=target.current_state,
        proposal=proposal_code,
        expected_benefit=benefit_code,
        tradeoffs=(tradeoff,),
        risk=risk_code,
        confidence=0.5,
        state=OptimizationProposalState.REVIEW_REQUIRED,
        review_required=True,
    )
    return EngineeringOptimizationProposal(
        **values,
        fingerprint=engineering_optimization_proposal_fingerprint(**values),
    )


def _change(
    target: EngineeringOptimizationTarget,
    proposal: EngineeringOptimizationProposal,
) -> OptimizationChangeProposal:
    values = dict(
        optimization_id=target.optimization_id,
        optimization_proposal_fingerprint=proposal.fingerprint,
        target_artifact_fingerprint=target.target_artifact_fingerprint,
        domain=target.domain,
        change_codes=(proposal.proposal,),
        review_required=True,
    )
    return OptimizationChangeProposal(
        **values,
        fingerprint=optimization_change_proposal_fingerprint(**values),
    )


def _revision(
    target: EngineeringOptimizationTarget,
    proposal: EngineeringOptimizationProposal,
) -> OptimizationRevisionPlan:
    validation_code = _DOMAIN_CODES[target.domain][3]
    values = dict(
        optimization_id=target.optimization_id,
        optimization_proposal_fingerprint=proposal.fingerprint,
        base_artifact_fingerprint=target.target_artifact_fingerprint,
        affected_domains=(target.domain,),
        planned_changes=(proposal.proposal,),
        validation_requirements=(validation_code,),
        review_required=True,
    )
    return OptimizationRevisionPlan(
        **values,
        fingerprint=optimization_revision_plan_fingerprint(**values),
    )


def _validation(
    target: EngineeringOptimizationTarget,
    proposal: EngineeringOptimizationProposal,
) -> OptimizationValidationPlan:
    values = dict(
        optimization_id=target.optimization_id,
        optimization_proposal_fingerprint=proposal.fingerprint,
        target_artifact_fingerprint=target.target_artifact_fingerprint,
        validation_requirements=(_DOMAIN_CODES[target.domain][3],),
        recommendation_only=True,
        review_required=True,
    )
    return OptimizationValidationPlan(
        **values,
        fingerprint=optimization_validation_plan_fingerprint(**values),
    )


def _ordered_findings(
    findings: set[OptimizationFindingCode],
) -> tuple[OptimizationFindingCode, ...]:
    return tuple(item for item in OptimizationFindingCode if item in findings)


def _create_engineering_optimization_service() -> EngineeringOptimizationPort:
    return _EngineeringOptimizationService()
