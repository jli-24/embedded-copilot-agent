import pytest

from embedded_copilot.tool_adapter.adapters.esp_idf import EspIdfToolAdapter
from embedded_copilot.tool_adapter.adapters.fake import FakeToolAdapter
from embedded_copilot.tool_adapter.adapters.jlink import JLinkToolAdapter
from embedded_copilot.tool_adapter.adapters.openocd import OpenOcdToolAdapter
from embedded_copilot.tool_adapter.adapters.platformio import PlatformIoToolAdapter
from embedded_copilot.tool_adapter.adapters.serial import SerialToolAdapter
from embedded_copilot.tool_adapter.contracts import ToolExecutionRequest, ToolType
from embedded_copilot.tool_adapter.exceptions import (
    FlashUnavailable,
    ObservationUnavailable,
    ToolUnavailable,
)


def _request() -> ToolExecutionRequest:
    return ToolExecutionRequest.create(
        tool_type=ToolType.ESP_IDF,
        operation="build",
        workspace_reference="workspace-1",
        artifact_reference="artifact-1",
        approval_reference="approval-1",
    )


def test_fake_is_deterministic_for_repeated_calls() -> None:
    adapter = FakeToolAdapter()
    results = [adapter.build(_request()) for _ in range(100)]
    assert all(result == results[0] for result in results)


@pytest.mark.parametrize("adapter", [EspIdfToolAdapter(), PlatformIoToolAdapter()])
def test_build_adapters_are_unavailable_without_executor(adapter) -> None:
    with pytest.raises(ToolUnavailable):
        adapter.build(_request())


@pytest.mark.parametrize("adapter", [OpenOcdToolAdapter(), JLinkToolAdapter()])
def test_flash_adapters_are_unavailable_without_executor(adapter) -> None:
    with pytest.raises(FlashUnavailable):
        adapter.flash(_request())


def test_serial_is_unavailable_without_transport() -> None:
    with pytest.raises(ObservationUnavailable):
        SerialToolAdapter().get_device("project-1")
