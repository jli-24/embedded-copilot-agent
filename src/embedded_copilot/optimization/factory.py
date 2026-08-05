from .contracts import OptimizationReasoningPort
from .service import OptimizationService


def create_optimization_service(
    reasoning: OptimizationReasoningPort | None = None,
) -> OptimizationService:
    return OptimizationService(reasoning)


__all__ = ["create_optimization_service"]
