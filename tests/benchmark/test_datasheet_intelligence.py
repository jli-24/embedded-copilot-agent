from __future__ import annotations

import copy
from pathlib import Path

import fitz

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.benchmark.datasets.datasheet import (
    SYNTHETIC_DATASHEET_FIXTURES,
    create_synthetic_datasheet_intelligence_dataset,
)
from embedded_copilot.benchmark.datasets.synthetic import (
    create_synthetic_foundation_dataset,
)
from embedded_copilot.benchmark.runner import BenchmarkRunner
from embedded_copilot.datasheet.adapters import (
    to_firmware_document,
    to_hardware_document,
    to_pcb_rule_document,
)
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.datasheet.parser import (
    MarkdownDatasheetParser,
    PDFDatasheetParser,
    RootedDatasheetSourceResolver,
)
from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.hardware.knowledge.retriever import HardwareKnowledgeRetriever
from embedded_copilot.input import InputLoader
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.knowledge.retriever import PCBKnowledgeRetriever


class _DatasheetTarget:
    def __init__(self, root: Path, domain: str) -> None:
        self.models: list[UnifiedDatasheetModel] = []
        self.document_ids: list[str] = []
        self._root = root
        self._domain = domain
        paths = {
            fixture_id: fixture.filename
            for fixture_id, fixture in SYNTHETIC_DATASHEET_FIXTURES.items()
        }
        resolver = RootedDatasheetSourceResolver(root, paths)
        self._markdown = MarkdownDatasheetParser(resolver)
        self._pdf = PDFDatasheetParser(resolver)

    def run(self, task: AgentTask):
        metadata = copy.deepcopy(task.metadata)
        fixture_id = metadata.pop("datasheet_fixture_id")
        fixture = SYNTHETIC_DATASHEET_FIXTURES[fixture_id]
        attachment = InputLoader(self._root).load(
            fixture.filename,
            attachment_id=fixture_id,
        )
        parser = self._pdf if fixture.filename.endswith(".pdf") else self._markdown
        model = parser.parse(attachment)
        self.models.append(model)
        clean_task = AgentTask(
            task_id=task.task_id,
            task_type=task.task_type,
            requirement=task.requirement,
            metadata=metadata,
        )
        if self._domain == "hardware":
            document = to_hardware_document(model)
            agent = HardwareAgent(
                retriever=HardwareKnowledgeRetriever([document])
            )
        elif self._domain == "firmware":
            document = to_firmware_document(model)
            agent = FirmwareAgent(
                retriever=FirmwareKnowledgeRetriever([document])
            )
        else:
            document = to_pcb_rule_document(model)
            agent = PCBAgent(retriever=PCBKnowledgeRetriever([document]))
        self.document_ids.append(document.id)
        return agent.run(clean_task)


def _write_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(36, 36, 560, 800), text, fontsize=10)
    document.save(path)
    document.close()


def test_synthetic_datasheet_dataset_is_separate_from_golden_cases() -> None:
    dataset = create_synthetic_datasheet_intelligence_dataset()

    assert dataset.name == "synthetic-datasheet-intelligence"
    assert [case.id for case in dataset.list_cases()] == [
        "synthetic-datasheet-esp32-s3",
        "synthetic-datasheet-stm32",
        "synthetic-datasheet-power-constraint",
    ]
    assert [case.category for case in dataset.list_cases()] == [
        "hardware",
        "firmware",
        "pcb",
    ]
    assert len(create_synthetic_foundation_dataset().list_cases()) == 7


def test_synthetic_datasheet_dataset_runs_complete_structured_chain(
    tmp_path: Path,
) -> None:
    for fixture in SYNTHETIC_DATASHEET_FIXTURES.values():
        path = tmp_path / fixture.filename
        if path.suffix == ".pdf":
            _write_pdf(path, fixture.content)
        else:
            path.write_text(fixture.content, encoding="utf-8")
    hardware = _DatasheetTarget(tmp_path, "hardware")
    firmware = _DatasheetTarget(tmp_path, "firmware")
    pcb = _DatasheetTarget(tmp_path, "pcb")

    report = BenchmarkRunner(
        {
            "HardwareAgent": hardware,
            "FirmwareAgent": firmware,
            "PCBAgent": pcb,
        }
    ).run(create_synthetic_datasheet_intelligence_dataset())

    assert report.passed_cases == 3
    assert report.failed_cases == 0
    targets = (hardware, firmware, pcb)
    assert all(len(target.models) == 1 for target in targets)
    assert all(len(target.document_ids) == 1 for target in targets)
    serialized = report.model_dump_json()
    assert str(tmp_path) not in serialized
    assert "Manufacturer:" not in serialized
    assert "PRIVATE_DOCUMENT_SENTINEL" not in serialized
