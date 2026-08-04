from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.toolchain.flash import (
    FlashPort,
    FlashRequest,
    FlashResult,
    FlashStatus,
    flash_result_fingerprint,
)
from embedded_copilot.toolchain.flash_adapter import FakeFlashAdapter
from embedded_copilot.toolchain.exceptions import (
    FlashApprovalRequired,
    FlashUnavailable,
)


def test_flash_requires_approval_and_default_is_unavailable() -> None:
    request = FlashRequest(
        firmware_reference="artifact-1",
        device_reference="board-1",
        approval_reference="approval-1",
        capability_reference="capability-1",
    )
    with pytest.raises(FlashUnavailable, match="FLASH_UNAVAILABLE"):
        FlashPort().flash(request)
    with pytest.raises(FlashApprovalRequired, match="FLASH_APPROVAL_REQUIRED"):
        FakeFlashAdapter().flash(
            FlashRequest(
                firmware_reference="artifact-1",
                device_reference="board-1",
                approval_reference=None,
                capability_reference="capability-1",
            )
        )


def test_fake_flash_result_is_safe_and_deterministic() -> None:
    request = FlashRequest(
        firmware_reference="artifact-1",
        device_reference="board-1",
        approval_reference="approval-1",
        capability_reference="capability-1",
    )
    values = tuple(FakeFlashAdapter().flash(request) for _ in range(100))
    assert len(set(values)) == 1
    assert values[0].status is FlashStatus.SUCCESS
    assert values[0].fingerprint == flash_result_fingerprint(values[0])
    with pytest.raises(ValidationError):
        FlashResult.model_validate({**values[0].model_dump(), "command": "flash"})
