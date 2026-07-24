from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from pydantic import Field, ValidationError

from embedded_copilot.benchmark.exceptions import BenchmarkDatasetError
from embedded_copilot.benchmark.models import BenchmarkCase
from embedded_copilot.schemas.result import ContractModel


class _DatasetPayload(ContractModel):
    name: str = Field(min_length=1)
    cases: list[BenchmarkCase]


def _copy_case(case: BenchmarkCase) -> BenchmarkCase:
    return BenchmarkCase.model_validate(case.model_dump(mode="python"))


class BenchmarkDataset:
    def __init__(
        self,
        name: str,
        cases: Sequence[BenchmarkCase] = (),
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise BenchmarkDatasetError("benchmark dataset name is invalid")
        self.name = name.strip()
        self._cases: dict[str, BenchmarkCase] = {}
        for case in cases:
            self.add_case(case)

    @classmethod
    def from_json(
        cls,
        payload: str | bytes | Mapping[str, object],
    ) -> "BenchmarkDataset":
        try:
            if isinstance(payload, (str, bytes)):
                raw = json.loads(payload)
            elif isinstance(payload, Mapping):
                raw = dict(payload)
            else:
                raise TypeError("dataset payload must be JSON data")
            validated = _DatasetPayload.model_validate(raw)
            return cls(validated.name, validated.cases)
        except (
            BenchmarkDatasetError,
            ValidationError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            raise BenchmarkDatasetError("benchmark dataset is invalid") from None

    def add_case(self, case: BenchmarkCase) -> None:
        if not isinstance(case, BenchmarkCase):
            raise BenchmarkDatasetError("benchmark dataset case is invalid")
        copied = _copy_case(case)
        key = copied.id.casefold()
        if key in self._cases:
            raise BenchmarkDatasetError("duplicate benchmark case id")
        self._cases[key] = copied

    def list_cases(self) -> list[BenchmarkCase]:
        return [_copy_case(case) for case in self._cases.values()]

    def get_case(self, case_id: str) -> BenchmarkCase:
        if not isinstance(case_id, str) or not case_id.strip():
            raise BenchmarkDatasetError("benchmark case id is invalid")
        try:
            return _copy_case(self._cases[case_id.strip().casefold()])
        except KeyError:
            raise BenchmarkDatasetError("benchmark case was not found") from None
