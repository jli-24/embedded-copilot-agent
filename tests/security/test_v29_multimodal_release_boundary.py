from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from embedded_copilot.multimodal_input.adapters.deepseek import DeepSeekReasoningAdapter
from embedded_copilot.multimodal_input.adapters.fake import FakeVisionAdapter
from embedded_copilot.multimodal_input.adapters.glm_v import GLMVisionAdapter
from embedded_copilot.multimodal_input.contracts import (
    EngineeringInterpretation,
    InputType,
    VisionObservation,
    VisionRequest,
    validate_observation,
)
from embedded_copilot.multimodal_input.exceptions import MultimodalUnavailable
from embedded_copilot.multimodal_input.service import MultimodalInputService


ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "src" / "embedded_copilot" / "multimodal_input"
ROUTE = ROOT / "src" / "embedded_copilot" / "api" / "multimodal_v29_routes.py"

FORBIDDEN_IMPORTS = (
    "embedded_copilot.agents",
    "embedded_copilot.engineering_memory",
    "embedded_copilot.knowledge_evolution",
    "embedded_copilot.knowledge_writer",
    "embedded_copilot.services",
    "embedded_copilot.tool_adapter",
    "embedded_copilot.tools",
    "embedded_copilot.workflow",
    "embedded_copilot.*_runtime",
    "langgraph",
)
FORBIDDEN_MODULES = {
    "chromadb",
    "httpx",
    "openai",
    "anthropic",
    "os",
    "pathlib",
    "requests",
    "socket",
    "sqlite3",
    "subprocess",
    "urllib",
    "websockets",
}
FORBIDDEN_ATTRIBUTES = {
    "apply",
    "execute",
    "mutate",
    "persist",
    "promote",
    "write_bytes",
    "write_text",
}
FORBIDDEN_FIELDS = {
    "binary",
    "credential",
    "device_handle",
    "file_content",
    "image_bytes",
    "provider",
    "runtime",
    "token",
}


def _request() -> VisionRequest:
    return VisionRequest.create(
        project_id="demo",
        source_reference="source:demo",
        input_type=InputType.IMAGE,
        context_fingerprint="sha256:" + "a" * 64,
    )


def _observation() -> VisionObservation:
    return FakeVisionAdapter().analyze(_request())


def _assert_no_forbidden_boundary(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in FORBIDDEN_MODULES, (path, alias.name)
                assert not any(
                    alias.name == prefix or alias.name.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_IMPORTS
                ), (path, alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".", 1)[0] not in FORBIDDEN_MODULES, (path, module)
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORTS
            ), (path, module)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_ATTRIBUTES, (path, node.attr)


def test_release_boundary_has_no_persistence_or_execution_dependencies() -> None:
    for path in (*PACKAGE.rglob("*.py"), ROUTE):
        _assert_no_forbidden_boundary(path)


def test_release_dtos_are_immutable_strict_and_fingerprint_bound() -> None:
    request = _request()
    observation = _observation()
    interpretation = EngineeringInterpretation.create(
        interpretation_id="interpretation:demo:1",
        observation_reference=observation.observation_id,
        summary="Observation remains a projection.",
        risk="Verification is still required.",
        confidence=0.7,
    )

    for model in (request, observation, interpretation):
        config = model.model_config
        assert config["frozen"] is True
        assert config["strict"] is True
        assert config["extra"] == "forbid"
        assert config["revalidate_instances"] == "always"
        assert model.fingerprint.startswith("sha256:")

    assert request == VisionRequest.model_validate(copy.deepcopy(request.model_dump()))
    assert observation == VisionObservation.model_validate(
        copy.deepcopy(observation.model_dump())
    )
    assert len({FakeVisionAdapter().analyze(_request()).fingerprint for _ in range(100)}) == 1

    with pytest.raises((ValidationError, TypeError)):
        request.project_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        VisionObservation.model_validate(
            {**observation.model_dump(), "image_bytes": b"raw image"}
        )
    with pytest.raises(ValidationError):
        VisionRequest.model_validate(
            {**request.model_dump(), "fingerprint": "sha256:" + "0" * 64}
        )

    for model in (VisionRequest, VisionObservation, EngineeringInterpretation):
        assert not set(model.model_fields).intersection(FORBIDDEN_FIELDS)


def test_reasoning_failure_preserves_observation_without_execution() -> None:
    class FailingReasoning:
        def analyze_observation(self, observation):
            raise RuntimeError("provider/runtime details")

    projection = MultimodalInputService(
        FakeVisionAdapter(), FailingReasoning()
    ).analyze(_request())
    assert projection.observation.observation_id == "observation:demo:1"
    assert projection.interpretation is None


def test_provider_adapters_fail_closed_without_executors() -> None:
    with pytest.raises(MultimodalUnavailable):
        GLMVisionAdapter().analyze(_request())
    with pytest.raises(MultimodalUnavailable):
        DeepSeekReasoningAdapter().analyze_observation(_observation())


def test_observation_validation_is_projection_only() -> None:
    observation = _observation()
    checked = validate_observation(observation)
    assert checked == observation
    assert checked is not observation
