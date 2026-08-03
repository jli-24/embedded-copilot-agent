"""Public v1.3 engineering observation contracts."""

from embedded_copilot.engineering_observation.factory import (
    create_engineering_observation_service,
)
from embedded_copilot.engineering_observation.models import (
    BuildObservationProjection,
    DebugCategory,
    EngineeringObservation,
    EngineeringObservationType,
    RepairProposal,
    build_observation_projection_fingerprint,
    canonical_observation_json,
    engineering_observation_fingerprint,
    repair_proposal_fingerprint,
)
from embedded_copilot.engineering_observation.service import (
    EngineeringObservationService,
)

__all__ = [
    "BuildObservationProjection",
    "DebugCategory",
    "EngineeringObservation",
    "EngineeringObservationService",
    "EngineeringObservationType",
    "RepairProposal",
    "build_observation_projection_fingerprint",
    "canonical_observation_json",
    "create_engineering_observation_service",
    "engineering_observation_fingerprint",
    "repair_proposal_fingerprint",
]
