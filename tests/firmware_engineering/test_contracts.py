from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.firmware_engineering.adapters.fake import (
    FakeFirmwareBuildPort,
    FakeFirmwareParserPort,
)
from embedded_copilot.firmware_engineering.contracts import (
    FirmwareFramework,
    FirmwareProjectSnapshot,
)


def test_fake_parser_is_deterministic_and_safe() -> None:
    values = [FakeFirmwareParserPort().parse("firmware:demo") for _ in range(100)]
    assert len({value.fingerprint for value in values}) == 1
    assert values[0].framework is FirmwareFramework.ESP_IDF
    assert "source" not in values[0].model_dump_json().lower()


def test_snapshot_is_frozen_tuple_only_and_tamper_checked() -> None:
    snapshot = FakeFirmwareParserPort().parse("firmware:demo")
    with pytest.raises(ValidationError):
        snapshot.project_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        FirmwareProjectSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "targets": list(snapshot.targets)}
        )
    with pytest.raises(ValidationError):
        FirmwareProjectSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )


def test_build_fake_is_deterministic() -> None:
    port = FakeFirmwareBuildPort()
    request = port.request("demo", "firmware:demo", "debug", "approval:1")
    values = [port.build(request) for _ in range(100)]
    assert len({value.fingerprint for value in values}) == 1
