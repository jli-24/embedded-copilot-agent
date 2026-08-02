"""Public Engineering Optimization Port contract."""

from __future__ import annotations

from typing import Protocol

from embedded_copilot.engineering_optimization.integration.inputs import (
    EngineeringOptimizationRequest,
)
from embedded_copilot.engineering_optimization.models import (
    EngineeringOptimizationReport,
)


class EngineeringOptimizationPort(Protocol):
    def analyze(
        self,
        request: EngineeringOptimizationRequest,
    ) -> EngineeringOptimizationReport: ...


__all__ = ("EngineeringOptimizationPort",)
