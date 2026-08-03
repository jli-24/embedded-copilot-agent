"""Factory for deterministic build observations."""

from embedded_copilot.engineering_observation.service import (
    EngineeringObservationService,
)


def create_engineering_observation_service() -> EngineeringObservationService:
    return EngineeringObservationService()
