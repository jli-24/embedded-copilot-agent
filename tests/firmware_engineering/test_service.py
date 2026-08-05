from __future__ import annotations

import pytest

from embedded_copilot.firmware_engineering.adapters.fake import FakeFirmwareBuildPort
from embedded_copilot.firmware_engineering.exceptions import BuildApprovalRequired
from embedded_copilot.firmware_engineering.service import FirmwareBuildService


def test_build_requires_approval_and_revalidates_result() -> None:
    port = FakeFirmwareBuildPort()
    service = FirmwareBuildService(port)
    request = port.request("demo", "firmware:demo", "debug", None)
    with pytest.raises(BuildApprovalRequired):
        service.build(request)
