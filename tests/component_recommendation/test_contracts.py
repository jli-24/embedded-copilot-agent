from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.component_recommendation import ComponentRecommendation


def test_component_recommendation_is_safe_projection() -> None:
    item = ComponentRecommendation(
        part_number="ESP32-S3",
        manufacturer="Espressif",
        reason="Verified engineering fit.",
        datasheet_reference="datasheet:esp32-s3",
        supplier_links=("https://supplier.example/esp32-s3",),
        alternatives=("STM32F4",),
    )
    assert item.model_config["strict"] is True
    with pytest.raises(ValidationError):
        ComponentRecommendation.model_validate(
            {**item.model_dump(), "supplier_links": ["https://supplier.example"]}
        )
    with pytest.raises(ValidationError):
        ComponentRecommendation.model_validate(
            {**item.model_dump(), "reason": "password=secret"}
        )
