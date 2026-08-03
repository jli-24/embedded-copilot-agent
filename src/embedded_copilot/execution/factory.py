"""Factory for the controlled build service."""

from embedded_copilot.execution.contracts import ESPIdfBuildExecutionPort
from embedded_copilot.execution.service import BuildExecutionService


def create_build_execution_service(
    *, build_port: ESPIdfBuildExecutionPort
) -> BuildExecutionService:
    return BuildExecutionService(build_port)
