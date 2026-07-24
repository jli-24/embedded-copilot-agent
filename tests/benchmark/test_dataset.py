from __future__ import annotations

import json

import pytest

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.exceptions import BenchmarkDatasetError
from embedded_copilot.benchmark.models import BenchmarkCase


def _case(case_id: str = "case-1") -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        name="Routing case",
        category="routing",
        input="firmware request",
        expected={"agents": ["FirmwareAgent"]},
        metadata={"nested": {"keep": True}},
    )


def test_dataset_add_list_get_and_mutation_isolation() -> None:
    case = _case()
    dataset = BenchmarkDataset(" foundation ")
    dataset.add_case(case)

    listed = dataset.list_cases()
    fetched = dataset.get_case(" CASE-1 ")
    listed[0].metadata["nested"]["keep"] = False  # type: ignore[index]
    fetched.expected["agents"].append("PCBAgent")  # type: ignore[union-attr]

    assert dataset.name == "foundation"
    assert dataset.list_cases() == [case]


def test_dataset_rejects_case_insensitive_duplicate_id() -> None:
    dataset = BenchmarkDataset("suite", [_case("Duplicate")])

    with pytest.raises(BenchmarkDatasetError, match="duplicate"):
        dataset.add_case(_case(" duplicate "))


def test_dataset_from_json_accepts_data_not_file_paths(tmp_path) -> None:
    payload = {
        "name": "json-suite",
        "cases": [_case().model_dump(mode="json")],
    }
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    from_text = BenchmarkDataset.from_json(json.dumps(payload))
    from_bytes = BenchmarkDataset.from_json(json.dumps(payload).encode())
    from_mapping = BenchmarkDataset.from_json(payload)

    assert from_text.list_cases() == [_case()]
    assert from_bytes.list_cases() == [_case()]
    assert from_mapping.list_cases() == [_case()]
    with pytest.raises(BenchmarkDatasetError):
        BenchmarkDataset.from_json(str(path))


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        {"name": "suite", "cases": [], "extra": True},
        {"name": "suite", "cases": [{"id": "bad"}]},
        {"name": "suite", "cases": [_case("x").model_dump(), _case("X").model_dump()]},
    ],
)
def test_dataset_from_json_rejects_malformed_payload(payload: object) -> None:
    with pytest.raises(BenchmarkDatasetError, match="dataset"):
        BenchmarkDataset.from_json(payload)  # type: ignore[arg-type]
