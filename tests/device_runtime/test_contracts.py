from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.device_runtime.contracts import (
    ConnectionStatus,
    DeviceConnection,
    DeviceSnapshot,
    DeviceType,
    device_connection_fingerprint,
    device_snapshot_fingerprint,
)
from embedded_copilot.device_runtime.adapters.fake import FakeDeviceAdapter
from embedded_copilot.device_runtime.adapters.serial import SerialDeviceAdapter
from embedded_copilot.device_runtime.exceptions import DeviceUnavailable


def test_device_dtos_are_strict_and_fingerprinted() -> None:
    connection = DeviceConnection.create(
        device_id="board-1",
        device_type=DeviceType.ESP32,
        connection_status=ConnectionStatus.CONNECTED,
    )
    assert connection.fingerprint == device_connection_fingerprint(connection)
    with pytest.raises(ValidationError):
        DeviceConnection.model_validate({**connection.model_dump(), "com_path": "COM3"})
    with pytest.raises(ValidationError):
        DeviceConnection.model_validate(
            {**connection.model_dump(), "device_id": "C:\\private"}
        )


def test_fake_device_is_deterministic_100_times() -> None:
    adapter = FakeDeviceAdapter()
    values = tuple(adapter.connect("board-1") for _ in range(100))
    assert len(set(values)) == 1


def test_snapshot_fingerprint_and_serial_unavailable() -> None:
    snapshot = DeviceSnapshot.create(
        project_id="demo",
        device_id="board-1",
        device_type=DeviceType.ESP32,
        connection_status=ConnectionStatus.CONNECTED,
    )
    assert snapshot.fingerprint == device_snapshot_fingerprint(snapshot)
    with pytest.raises(DeviceUnavailable, match="DEVICE_UNAVAILABLE"):
        SerialDeviceAdapter().connect("board-1")
