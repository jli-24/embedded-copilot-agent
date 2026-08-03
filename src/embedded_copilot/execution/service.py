"""Controlled build service with one injected host delegation."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.execution.contracts import ESPIdfBuildExecutionPort
from embedded_copilot.execution.exceptions import BuildExecutionRejected
from embedded_copilot.execution.models import (
    BuildApprovalStatus,
    BuildExecutionRequest,
    BuildResult,
    BuildStatus,
    ESPIdfBuildInvocation,
    HostBuildResult,
    build_invocation_fingerprint,
    build_result_fingerprint,
)


class BuildExecutionService:
    __slots__ = ("_build_port",)

    def __init__(self, build_port: ESPIdfBuildExecutionPort) -> None:
        if not isinstance(build_port, ESPIdfBuildExecutionPort):
            raise TypeError("build_port is invalid")
        self._build_port = build_port

    async def execute(self, request: BuildExecutionRequest) -> BuildResult:
        try:
            if type(request) is not BuildExecutionRequest:
                raise ValueError("typed build request is required")
            checked = BuildExecutionRequest.model_validate(
                request.model_copy(deep=True)
            )
        except (TypeError, ValueError, ValidationError):
            raise BuildExecutionRejected("build execution was rejected") from None

        if checked.approval.status is not BuildApprovalStatus.APPROVED:
            return _result(
                checked,
                BuildStatus.BLOCKED,
                ("BUILD_APPROVAL_REQUIRED",),
                (),
            )

        invocation_values = {
            "build_id": checked.build_id,
            "project_id": checked.proposal.project_id,
            "proposal_fingerprint": checked.proposal.fingerprint,
            "source_file_fingerprints": tuple(
                sorted(item.fingerprint for item in checked.proposal.files)
            ),
            "platform": checked.proposal.platform,
            "requested_at": checked.requested_at,
        }
        invocation = ESPIdfBuildInvocation(
            **invocation_values,
            fingerprint=build_invocation_fingerprint(**invocation_values),
        )
        try:
            host_result = await self._build_port.build(invocation.model_copy(deep=True))
            if type(host_result) is not HostBuildResult:
                raise ValueError("typed host result is required")
            checked_result = HostBuildResult.model_validate(
                host_result.model_copy(deep=True)
            )
        except Exception:  # noqa: BLE001 - host failures become safe results
            return _result(
                checked,
                BuildStatus.UNAVAILABLE,
                ("BUILD_EXECUTION_UNAVAILABLE",),
                (),
            )
        return _result(
            checked,
            checked_result.status,
            checked_result.diagnostic_codes,
            checked_result.symbol_references,
        )


def _result(
    request: BuildExecutionRequest,
    status: BuildStatus,
    diagnostic_codes: tuple[str, ...],
    symbol_references: tuple[str, ...],
) -> BuildResult:
    values = {
        "build_id": request.build_id,
        "project_id": request.proposal.project_id,
        "proposal_fingerprint": request.proposal.fingerprint,
        "status": status,
        "diagnostic_codes": diagnostic_codes,
        "symbol_references": symbol_references,
        "observed_at": request.requested_at,
    }
    return BuildResult(**values, fingerprint=build_result_fingerprint(**values))
