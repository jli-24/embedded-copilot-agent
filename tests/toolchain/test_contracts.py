from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.toolchain.contracts import (
    BuildResult,
    BuildStatus,
    FlashPort,
    RunPort,
    ToolchainArtifactReference,
    ToolchainSnapshot,
    WorkspaceStatus,
    build_result_fingerprint,
    toolchain_snapshot_fingerprint,
)
from embedded_copilot.toolchain.exceptions import (
    FlashUnavailable,
    RunUnavailable,
    ToolchainUnavailable,
)


def _result() -> BuildResult:
    return BuildResult.create(
        status=BuildStatus.SUCCESS,
        artifact_reference=ToolchainArtifactReference(
            reference_id="artifact-1", artifact_type="FIRMWARE"
        ),
        summary="Build completed.",
    )


def test_build_result_is_safe_and_fingerprinted() -> None:
    result = _result()
    assert result.fingerprint == build_result_fingerprint(result)
    with pytest.raises(ValidationError):
        BuildResult.model_validate({**result.model_dump(), "command": "idf.py"})


def test_toolchain_snapshot_fingerprint_is_stable() -> None:
    snapshot = ToolchainSnapshot.create(
        build_status=BuildStatus.SUCCESS,
        artifact=_result().artifact_reference,
        workspace_status=WorkspaceStatus.APPROVED,
    )
    assert snapshot.fingerprint == toolchain_snapshot_fingerprint(snapshot)


def test_flash_and_run_are_unavailable_by_default() -> None:
    with pytest.raises(FlashUnavailable, match="FLASH_UNAVAILABLE"):
        FlashPort().flash("workspace-1")
    with pytest.raises(RunUnavailable, match="RUN_UNAVAILABLE"):
        RunPort().run("workspace-1")


def test_production_factory_does_not_enable_build_without_injected_executor() -> None:
    from embedded_copilot.toolchain.factory import create_toolchain_service

    with pytest.raises(ToolchainUnavailable, match="TOOLCHAIN_UNAVAILABLE"):
        create_toolchain_service().build("workspace-1")
