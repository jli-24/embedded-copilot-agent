from __future__ import annotations

from typing import Protocol, runtime_checkable

from .contracts import ToolExecutionRequest, ToolExecutionResult


@runtime_checkable
class BuildExecutorPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...


@runtime_checkable
class FlashExecutorPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...


@runtime_checkable
class SerialTransportPort(Protocol):
    def observe(self, device_reference: str) -> object: ...


@runtime_checkable
class DebugExecutorPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...


@runtime_checkable
class JLinkExecutorPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...


def call_build_executor(
    executor: object, request: ToolExecutionRequest
) -> ToolExecutionResult:
    method = getattr(executor, "execute", None) or getattr(executor, "build", None)
    if not callable(method):
        raise TypeError("build executor is unavailable")
    return method(request)


def call_flash_executor(
    executor: object, request: ToolExecutionRequest
) -> ToolExecutionResult:
    method = getattr(executor, "execute", None) or getattr(executor, "flash", None)
    if not callable(method):
        raise TypeError("flash executor is unavailable")
    return method(request)


__all__ = [
    "BuildExecutorPort",
    "call_build_executor",
    "call_flash_executor",
    "DebugExecutorPort",
    "FlashExecutorPort",
    "JLinkExecutorPort",
    "SerialTransportPort",
]
