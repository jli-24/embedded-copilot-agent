"""Composition root for caller-owned Engineering Execution Ports."""

from __future__ import annotations

from embedded_copilot.engineering_execution.contracts import (
    BuildPort,
    DebugPort,
    FlashPort,
)
from embedded_copilot.engineering_execution.facade import EngineeringExecutionRuntime
from embedded_copilot.engineering_execution.runtime import _EngineeringExecutionService


def _validate_port(port: object | None, *, method: str) -> None:
    if port is None:
        return
    if (
        not callable(getattr(port, method, None))
        or getattr(type(port), "metadata", None) is None
    ):
        raise TypeError("engineering execution port is invalid")


def create_engineering_execution_runtime(
    *,
    build_port: BuildPort | None = None,
    flash_port: FlashPort | None = None,
    debug_port: DebugPort | None = None,
) -> EngineeringExecutionRuntime:
    _validate_port(build_port, method="build")
    _validate_port(flash_port, method="flash")
    _validate_port(debug_port, method="debug")
    return EngineeringExecutionRuntime._compose(
        _EngineeringExecutionService(
            build_port=build_port,
            flash_port=flash_port,
            debug_port=debug_port,
        )
    )
