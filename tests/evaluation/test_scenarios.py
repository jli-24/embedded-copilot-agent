from __future__ import annotations

from embedded_copilot.evaluation.scenarios import create_default_evaluation_dataset


def test_default_scenario_reuses_three_existing_integration_cases() -> None:
    dataset = create_default_evaluation_dataset()
    cases = dataset.list_cases()

    assert dataset.name == "synthetic-embedded-copilot-integration"
    assert [case.id for case in cases] == [
        "synthetic-esp32-camera-integration",
        "synthetic-firmware-debug-integration",
        "synthetic-pcb-review-integration",
    ]
    assert all(case.category == "end_to_end" for case in cases)


def test_default_scenario_returns_deep_isolated_dataset() -> None:
    first = create_default_evaluation_dataset()
    first_case = first.list_cases()[0]
    first_case.metadata["mutated"] = True

    second_case = create_default_evaluation_dataset().list_cases()[0]

    assert "mutated" not in second_case.metadata
