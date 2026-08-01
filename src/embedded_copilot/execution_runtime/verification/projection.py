"""Typed verification result validation."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from embedded_copilot.execution_runtime.exceptions import ExecutionRejected

_Model = TypeVar("_Model", bound=BaseModel)


def copy_exact(value: object, expected_type: type[_Model]) -> _Model:
    """Deep-copy and revalidate a typed contract without serialization."""
    if type(value) is not expected_type:
        raise ExecutionRejected("execution request was rejected")
    try:
        copied = value.model_copy(deep=True)
        return expected_type.model_validate(copied)
    except Exception:
        raise ExecutionRejected("execution request was rejected") from None


__all__: tuple[str, ...] = ()
