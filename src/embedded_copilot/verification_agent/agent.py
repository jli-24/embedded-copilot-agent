from __future__ import annotations

import copy
from dataclasses import dataclass

from embedded_copilot.verification_agent.audit import emit_audit
from embedded_copilot.verification_agent.exceptions import (
    VerificationCheckerUnavailable,
    VerificationRequestRejected,
)
from embedded_copilot.verification_agent.models import (
    VerificationAuditEventType,
    VerificationCheckResult,
    VerificationRequest,
    VerificationResult,
    VerificationSubject,
    VerificationSubjectType,
)
from embedded_copilot.verification_agent.ports import (
    VerificationAuditSink,
    VerificationCheckerPort,
    VerificationPort,
)
from embedded_copilot.verification_agent.rules import aggregate_results


@dataclass(frozen=True, slots=True)
class _CheckerAdapter:
    name: str
    supported_subjects: tuple[VerificationSubjectType, ...]
    checker: VerificationCheckerPort


class VerificationAgent:
    __slots__ = ("_verification_port",)

    def __init__(self, verification_port: VerificationPort) -> None:
        raise TypeError("VerificationAgent must be created by the composition factory")

    @classmethod
    def _compose(cls, verification_port: VerificationPort) -> "VerificationAgent":
        if not isinstance(verification_port, VerificationPort):
            raise TypeError("verification port is invalid")
        agent = object.__new__(cls)
        object.__setattr__(agent, "_verification_port", verification_port)
        return agent

    def verification_port(self) -> VerificationPort:
        return self._verification_port


class _VerificationPort:
    __slots__ = ("_audit_sink", "_checkers")

    def __init__(
        self,
        checkers: tuple[_CheckerAdapter, ...],
        audit_sink: VerificationAuditSink,
    ) -> None:
        self._checkers = checkers
        self._audit_sink = audit_sink

    def verify(self, request: VerificationRequest) -> VerificationResult:
        request = _validated_request(request)
        self._audit(VerificationAuditEventType.VERIFICATION_REQUESTED, request)
        applicable = tuple(
            adapter
            for adapter in self._checkers
            if request.subject_type in adapter.supported_subjects
        )
        if not applicable:
            self._audit(VerificationAuditEventType.VERIFICATION_FAILED, request)
            raise VerificationCheckerUnavailable
        results: list[VerificationCheckResult] = []
        for adapter in applicable:
            try:
                subject = _isolated_subject(request.subject)
                raw = adapter.checker.verify(subject)
                result = VerificationCheckResult.model_validate(
                    copy.deepcopy(raw.model_dump(mode="python"))
                )
            except Exception:
                self._audit(VerificationAuditEventType.VERIFICATION_FAILED, request)
                raise VerificationCheckerUnavailable from None
            results.append(result)
        result = aggregate_results(request.request_id, tuple(results))
        self._audit(VerificationAuditEventType.VERIFICATION_COMPLETED, request)
        return result

    def _audit(
        self,
        event_type: VerificationAuditEventType,
        request: VerificationRequest,
    ) -> None:
        emit_audit(
            self._audit_sink,
            event_type=event_type,
            request_id=request.request_id,
            subject_type=request.subject_type,
            timestamp=request.requested_at,
        )


def _validated_request(value: VerificationRequest) -> VerificationRequest:
    try:
        return VerificationRequest.model_validate(
            copy.deepcopy(value.model_dump(mode="python"))
        )
    except Exception:
        raise VerificationRequestRejected from None


def _isolated_subject(subject: VerificationSubject) -> VerificationSubject:
    return type(subject).model_validate(
        copy.deepcopy(subject.model_dump(mode="python"))
    )
