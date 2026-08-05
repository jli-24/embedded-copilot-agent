from .adapters.fake import FakeOptimizationAnalysisPort, FakeOptimizationApprovalPort


def create_optimization_ports() -> tuple[None, None]:
    return None, None


__all__ = [
    "FakeOptimizationAnalysisPort",
    "FakeOptimizationApprovalPort",
    "create_optimization_ports",
]
