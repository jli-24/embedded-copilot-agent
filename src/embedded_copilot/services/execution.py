from __future__ import annotations

import copy
from collections import OrderedDict
from enum import StrEnum
from threading import Lock

from pydantic import Field

from embedded_copilot.integration.report import EngineeringReport
from embedded_copilot.schemas.result import ContractModel


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionError(RuntimeError):
    """Base error for product analysis execution state."""


class ExecutionCapacityError(ExecutionError):
    """Raised when every bounded registry slot is active."""


class ExecutionNotFoundError(ExecutionError):
    """Raised when an execution identifier is unknown."""


class ReportNotReadyError(ExecutionError):
    """Raised when an execution has no completed report."""


class ExecutionSnapshot(ContractModel):
    execution_id: str = Field(min_length=1)
    status: ExecutionStatus
    error: str | None = None


class _ExecutionRecord(ContractModel):
    execution_id: str = Field(min_length=1)
    status: ExecutionStatus
    error: str | None = None
    report: EngineeringReport | None = None


class ExecutionRegistry:
    """Bounded process-local status and report registry."""

    def __init__(self, *, capacity: int = 100) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("execution registry capacity is invalid")
        self._capacity = capacity
        self._records: OrderedDict[str, _ExecutionRecord] = OrderedDict()
        self._lock = Lock()

    def create(self, execution_id: str) -> ExecutionSnapshot:
        record = _ExecutionRecord(
            execution_id=execution_id,
            status=ExecutionStatus.QUEUED,
        )
        with self._lock:
            if record.execution_id in self._records:
                raise ValueError("execution identifier already exists")
            self._make_room()
            self._records[record.execution_id] = record
        return self._snapshot(record)

    def mark_running(self, execution_id: str) -> ExecutionSnapshot:
        return self._replace(execution_id, status=ExecutionStatus.RUNNING)

    def mark_completed(
        self,
        execution_id: str,
        report: EngineeringReport,
    ) -> ExecutionSnapshot:
        isolated = EngineeringReport.model_validate(
            copy.deepcopy(report.model_dump(mode="python"))
        )
        return self._replace(
            execution_id,
            status=ExecutionStatus.COMPLETED,
            report=isolated,
        )

    def mark_failed(self, execution_id: str, error: str) -> ExecutionSnapshot:
        return self._replace(
            execution_id,
            status=ExecutionStatus.FAILED,
            error=error,
        )

    def get(self, execution_id: str) -> ExecutionSnapshot | None:
        with self._lock:
            record = self._records.get(execution_id)
            return self._snapshot(record) if record is not None else None

    def require(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = self.get(execution_id)
        if snapshot is None:
            raise ExecutionNotFoundError("execution was not found")
        return snapshot

    def report(self, execution_id: str) -> EngineeringReport:
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                raise ExecutionNotFoundError("execution was not found")
            if record.status is not ExecutionStatus.COMPLETED or record.report is None:
                raise ReportNotReadyError("execution report is not ready")
            return EngineeringReport.model_validate(
                copy.deepcopy(record.report.model_dump(mode="python"))
            )

    def _make_room(self) -> None:
        if len(self._records) < self._capacity:
            return
        terminal = {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
        }
        for identifier, record in self._records.items():
            if record.status in terminal:
                del self._records[identifier]
                return
        raise ExecutionCapacityError("analysis execution capacity is full")

    def _replace(
        self,
        execution_id: str,
        *,
        status: ExecutionStatus,
        error: str | None = None,
        report: EngineeringReport | None = None,
    ) -> ExecutionSnapshot:
        with self._lock:
            current = self._records.get(execution_id)
            if current is None:
                raise ExecutionNotFoundError("execution was not found")
            replacement = _ExecutionRecord(
                execution_id=execution_id,
                status=status,
                error=error,
                report=report,
            )
            self._records[execution_id] = replacement
            return self._snapshot(replacement)

    @staticmethod
    def _snapshot(record: _ExecutionRecord) -> ExecutionSnapshot:
        return ExecutionSnapshot(
            execution_id=record.execution_id,
            status=record.status,
            error=record.error,
        )
