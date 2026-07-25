from __future__ import annotations

from pathlib import Path

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.api.models import AnalyzeRequest
from embedded_copilot.benchmark.models import BenchmarkCase
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.integration.report import EngineeringReport


def test_extension_sources_have_no_forbidden_execution_or_network_backends() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "embedded_copilot"
    files = [
        *sorted((root / "engineering").glob("*.py")),
        *sorted((root / "datasheet" / "extensions" / "real_pdf").glob("*.py")),
        *sorted((root / "firmware" / "review").glob("*.py")),
    ]
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in files)

    for forbidden in (
        "import fitz",
        "import requests",
        "import httpx",
        "import socket",
        "import subprocess",
        "pytesseract",
        "tesseract",
        "ocrmypdf",
        "os.system",
        "subprocess.run",
        "subprocess.popen",
    ):
        assert forbidden not in source


def test_public_model_field_sets_remain_unchanged() -> None:
    assert tuple(AgentTask.model_fields) == (
        "task_id",
        "task_type",
        "requirement",
        "metadata",
    )
    assert tuple(AnalyzeRequest.model_fields) == ("request", "attachments", "options")
    assert tuple(UnifiedDatasheetModel.model_fields) == (
        "component",
        "pins",
        "interfaces",
        "electrical_specs",
        "power_requirements",
        "metadata",
    )
    assert tuple(FirmwareProject.model_fields) == (
        "name",
        "platform",
        "framework",
        "files",
        "structure",
        "metadata",
    )
    assert tuple(HardwarePlan.model_fields) == (
        "project_name",
        "platform",
        "mcu",
        "components",
        "interfaces",
        "power_requirements",
        "constraints",
        "rationale",
        "metadata",
    )
    assert tuple(EngineeringReport.model_fields) == (
        "summary",
        "hardware_section",
        "firmware_section",
        "pcb_section",
        "debug_section",
        "recommendations",
        "trace",
    )
    assert tuple(BenchmarkCase.model_fields) == (
        "id",
        "name",
        "category",
        "input",
        "expected",
        "metadata",
    )
