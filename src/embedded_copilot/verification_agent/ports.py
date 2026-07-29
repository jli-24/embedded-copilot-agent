from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.verification_agent.models import (
    VerificationAuditEvent,
    VerificationCheckResult,
    VerificationRequest,
    VerificationResult,
    VerificationSubject,
    VerificationSubjectType,
)


@runtime_checkable
class VerificationPort(Protocol):
    def verify(self, request: VerificationRequest) -> VerificationResult: ...


@runtime_checkable
class VerificationCheckerPort(Protocol):
    @property
    def checker_name(self) -> str: ...

    @property
    def supported_subjects(self) -> tuple[VerificationSubjectType, ...]: ...

    def verify(self, subject: VerificationSubject) -> VerificationCheckResult: ...


@runtime_checkable
class VerificationAuditSink(Protocol):
    def record(self, event: VerificationAuditEvent) -> None: ...
