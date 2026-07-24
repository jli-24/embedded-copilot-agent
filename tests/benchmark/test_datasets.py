from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_foundation_dataset,
)


def test_synthetic_dataset_explicitly_covers_every_category() -> None:
    dataset = create_synthetic_foundation_dataset()
    cases = dataset.list_cases()

    assert {case.category for case in cases} == {
        "routing",
        "firmware",
        "hardware",
        "pcb",
        "debug",
        "knowledge",
        "end_to_end",
    }
    assert all(case.metadata == {"fixture_kind": "synthetic"} for case in cases)
    serialized = " ".join(case.model_dump_json() for case in cases)
    assert "C:/" not in serialized
    assert "C:\\" not in serialized
    assert "password" not in serialized.casefold()
    assert "private" not in serialized.casefold()
