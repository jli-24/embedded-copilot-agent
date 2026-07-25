from __future__ import annotations

from embedded_copilot.benchmark.datasets.real_engineering import (
    create_synthetic_real_engineering_dataset,
)


def test_real_engineering_dataset_contains_three_isolated_extension_cases() -> None:
    dataset = create_synthetic_real_engineering_dataset()
    cases = dataset.list_cases()

    assert dataset.name == "synthetic-real-engineering"
    assert [case.id for case in cases] == [
        "real-engineering-esp32-s3-datasheet",
        "real-engineering-esp32-firmware-review",
        "real-engineering-datasheet-firmware-crosscheck",
    ]
    assert [case.category for case in cases] == [
        "hardware",
        "firmware",
        "end_to_end",
    ]
    assert all(case.metadata["fixture_kind"] == "synthetic_real_engineering" for case in cases)
    assert cases[0].expected["interfaces"] == ["SPI", "I2C", "UART", "USB"]
    assert cases[1].metadata["expected_rule"] == "freertos-task-starvation"
    assert cases[2].metadata["expected_severity"] == "high"
