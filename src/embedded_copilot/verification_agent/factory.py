from __future__ import annotations

from embedded_copilot.verification_agent.agent import (
    VerificationAgent,
    _CheckerAdapter,
    _VerificationPort,
)
from embedded_copilot.verification_agent.models import (
    VerificationSubjectType,
    checker_name,
)
from embedded_copilot.verification_agent.ports import (
    VerificationAuditSink,
    VerificationCheckerPort,
)


def create_verification_agent(
    *,
    checkers: tuple[VerificationCheckerPort, ...],
    audit_sink: VerificationAuditSink,
) -> VerificationAgent:
    if not isinstance(checkers, tuple):
        raise TypeError("checkers must be a tuple")
    if not checkers:
        raise ValueError("checkers must not be empty")
    if not isinstance(audit_sink, VerificationAuditSink):
        raise TypeError("audit sink is invalid")
    adapters: list[_CheckerAdapter] = []
    names: list[str] = []
    for checker in checkers:
        try:
            valid = isinstance(checker, VerificationCheckerPort)
        except Exception:
            raise TypeError("verification checker is invalid") from None
        if not valid:
            raise TypeError("verification checker is invalid")
        try:
            name = checker_name(checker.checker_name)
            subjects = checker.supported_subjects
        except Exception:
            raise TypeError("verification checker contract is invalid") from None
        if not isinstance(subjects, tuple) or not subjects:
            raise ValueError("supported subjects must be a non-empty tuple")
        if any(not isinstance(item, VerificationSubjectType) for item in subjects):
            raise TypeError("supported subject is invalid")
        if len(subjects) != len(set(subjects)):
            raise ValueError("supported subjects must be unique")
        names.append(name)
        adapters.append(
            _CheckerAdapter(
                name=name,
                supported_subjects=subjects,
                checker=checker,
            )
        )
    if len(names) != len(set(names)):
        raise ValueError("checker names must be unique")
    return VerificationAgent._compose(_VerificationPort(tuple(adapters), audit_sink))
