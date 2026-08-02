"""Framework-independent, proposal-only Engineering Optimization Layer."""

from embedded_copilot.engineering_optimization.contracts import (
    EngineeringOptimizationPort,
)
from embedded_copilot.engineering_optimization.exceptions import (
    EngineeringOptimizationError,
    EngineeringOptimizationRejected,
)
from embedded_copilot.engineering_optimization.facade import (
    EngineeringOptimizationRuntime,
)
from embedded_copilot.engineering_optimization.factory import (
    create_engineering_optimization_runtime,
)
from embedded_copilot.engineering_optimization.integration.inputs import (
    EngineeringOptimizationRequest,
    engineering_optimization_request_fingerprint,
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
    canonical_optimization_json,
    engineering_optimization_proposal_fingerprint,
    engineering_optimization_report_fingerprint,
    engineering_optimization_review_fingerprint,
    engineering_tradeoff_fingerprint,
    optimization_change_proposal_fingerprint,
    optimization_revision_plan_fingerprint,
    optimization_target_fingerprint,
    optimization_validation_plan_fingerprint,
)

__all__ = (
    "EngineeringOptimizationError",
    "EngineeringOptimizationPort",
    "EngineeringOptimizationProposal",
    "EngineeringOptimizationRejected",
    "EngineeringOptimizationReport",
    "EngineeringOptimizationRequest",
    "EngineeringOptimizationReviewProjection",
    "EngineeringOptimizationRuntime",
    "EngineeringOptimizationTarget",
    "EngineeringTradeoffProjection",
    "OptimizationChangeProposal",
    "OptimizationDomain",
    "OptimizationFindingCode",
    "OptimizationProposalState",
    "OptimizationRevisionPlan",
    "OptimizationReviewState",
    "OptimizationValidationPlan",
    "canonical_optimization_json",
    "create_engineering_optimization_runtime",
    "engineering_optimization_proposal_fingerprint",
    "engineering_optimization_report_fingerprint",
    "engineering_optimization_request_fingerprint",
    "engineering_optimization_review_fingerprint",
    "engineering_tradeoff_fingerprint",
    "optimization_change_proposal_fingerprint",
    "optimization_revision_plan_fingerprint",
    "optimization_target_fingerprint",
    "optimization_validation_plan_fingerprint",
)
