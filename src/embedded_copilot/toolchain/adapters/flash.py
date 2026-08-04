from __future__ import annotations

from ..exceptions import FlashApprovalRequired, FlashCapabilityRequired
from ..flash import FlashPort, FlashRequest, FlashResult, FlashStatus


class FakeFlashAdapter(FlashPort):
    def flash(self, request: FlashRequest) -> FlashResult:
        checked = request
        if checked.capability_reference is None:
            raise FlashCapabilityRequired()
        if checked.approval_reference is None:
            raise FlashApprovalRequired()
        return FlashResult.create(
            status=FlashStatus.SUCCESS,
            firmware_reference=checked.firmware_reference,
            device_reference=checked.device_reference,
            summary="Deterministic flash result for review.",
        )


__all__ = ["FakeFlashAdapter"]
