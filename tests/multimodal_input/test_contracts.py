from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.multimodal_input.adapters.fake import FakeVisionAdapter
from embedded_copilot.multimodal_input.contracts import InputType, VisionRequest


def _request() -> VisionRequest:
    return VisionRequest.create(
        project_id="demo",
        source_reference="source:demo",
        input_type=InputType.IMAGE,
        context_fingerprint="sha256:" + "a" * 64,
    )


def test_fake_observation_is_deterministic_and_dto_is_frozen() -> None:
    request = _request()
    values = [FakeVisionAdapter().analyze(request) for _ in range(100)]
    assert len({value.fingerprint for value in values}) == 1
    with pytest.raises((ValidationError, TypeError)):
        values[0].project_id = "other"  # type: ignore[misc]


def test_request_rejects_tuple_violation_and_fingerprint_tampering() -> None:
    with pytest.raises(ValidationError):
        VisionRequest.model_validate(
            {
                **_request().model_dump(mode="python"),
                "fingerprint": "sha256:" + "0" * 64,
            }
        )


def test_contracts_normalize_safe_text_and_reject_raw_input_fields() -> None:
    request = VisionRequest.create(
        project_id="cafe\u0301",
        source_reference="source:demo",
        input_type=InputType.IMAGE,
        context_fingerprint="sha256:" + "a" * 64,
    )
    assert request.project_id == "café"
    config = type(request).model_config
    assert config["frozen"] is True
    assert config["strict"] is True
    assert config["extra"] == "forbid"
    assert config["revalidate_instances"] == "always"

    with pytest.raises(ValidationError):
        VisionRequest.model_validate({
            **request.model_dump(mode="python"),
            "image_bytes": b"raw image",
        })
    with pytest.raises((ValidationError, ValueError)):
        VisionRequest.model_validate({
            **request.model_dump(mode="python"),
            "source_reference": "source:demo\nunsafe",
        })
