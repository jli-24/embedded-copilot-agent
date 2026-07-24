from __future__ import annotations

import copy
from pathlib import Path

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.benchmark.datasets.pcb import (
    SYNTHETIC_PCB_FIXTURES,
    create_synthetic_pcb_intelligence_dataset,
)
from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_foundation_dataset,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.input import InputLoader
from embedded_copilot.pcb.adapters import attach_pcb_model
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.models import UnifiedPCBModel
from embedded_copilot.pcb.parser import KiCadPCBParser, RootedPCBSourceResolver


class _PCBIntelligenceTarget:
    def __init__(self, root: Path) -> None:
        self._root = root
        self.models: list[UnifiedPCBModel] = []
        paths = {
            fixture_id: fixture.filename
            for fixture_id, fixture in SYNTHETIC_PCB_FIXTURES.items()
        }
        self._parser = KiCadPCBParser(RootedPCBSourceResolver(root, paths))
        self._agent = PCBAgent()

    def run(self, task: AgentTask):
        metadata = copy.deepcopy(task.metadata)
        fixture_id = metadata.pop("pcb_fixture_id")
        fixture = SYNTHETIC_PCB_FIXTURES[fixture_id]
        attachment = InputLoader(self._root).load(
            fixture.filename,
            attachment_id=fixture_id,
            content_type="application/x-kicad-pcb",
        )
        model = self._parser.parse(attachment)
        self.models.append(model)
        clean_task = AgentTask(
            task_id=task.task_id,
            task_type=task.task_type,
            requirement=task.requirement,
            metadata=metadata,
        )
        return self._agent.run(attach_pcb_model(clean_task, model))


def test_synthetic_pcb_dataset_is_separate_and_preserves_golden_cases() -> None:
    dataset = create_synthetic_pcb_intelligence_dataset()

    assert dataset.name == "synthetic-pcb-intelligence"
    assert [case.id for case in dataset.list_cases()] == [
        "synthetic-pcb-simple-esp32",
        "synthetic-pcb-power-issue",
        "synthetic-pcb-floating-net",
    ]
    assert all(case.category == "pcb" for case in dataset.list_cases())
    assert len(create_synthetic_foundation_dataset().list_cases()) == 7


def test_synthetic_pcb_dataset_runs_complete_structured_chain(tmp_path: Path) -> None:
    for fixture in SYNTHETIC_PCB_FIXTURES.values():
        (tmp_path / fixture.filename).write_text(fixture.content, encoding="utf-8")
    target = _PCBIntelligenceTarget(tmp_path)

    report = BenchmarkRunner({"PCBAgent": target}).run(
        create_synthetic_pcb_intelligence_dataset()
    )

    assert report.passed_cases == 3
    assert report.failed_cases == 0
    assert len(target.models) == 3
    assert all(isinstance(model, UnifiedPCBModel) for model in target.models)
    serialized = report.model_dump_json()
    assert str(tmp_path) not in serialized
    assert "(kicad_pcb" not in serialized
