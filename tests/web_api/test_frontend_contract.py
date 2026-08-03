from __future__ import annotations

import json
from pathlib import Path


def test_frontend_manifest_and_routes_are_declared() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    dependencies = package["dependencies"]
    assert {"react", "react-dom", "react-router-dom", "@xyflow/react"} <= set(
        dependencies
    )
    assert "tailwindcss" in package["devDependencies"]

    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    assert 'path="/"' in app
    assert 'path="/projects/:projectId"' in app


def test_frontend_pipeline_and_actions_are_safe() -> None:
    pipeline = Path("frontend/src/components/EngineeringPipeline.tsx").read_text(
        encoding="utf-8"
    )
    actions = Path("frontend/src/components/ActionCenter.tsx").read_text(
        encoding="utf-8"
    )
    attachment = Path("frontend/src/components/AttachmentPanel.tsx").read_text(
        encoding="utf-8"
    )

    for stage in (
        "Requirement",
        "Architecture",
        "Hardware",
        "Firmware",
        "Validation",
        "Artifact",
        "Execution",
        "Feedback",
        "Optimization",
    ):
        assert stage in pipeline
    assert "ReactFlow" in pipeline
    assert "disabled" in actions
    for label in (
        "Generate Proposal",
        "Build Firmware",
        "Flash Device",
        "Debug Session",
        "Hardware Test",
        "PID Optimization",
    ):
        assert label in actions
    for forbidden in ("FileReader", "arrayBuffer(", ".text(", "base64"):
        assert forbidden not in attachment


def test_frontend_exposes_v13_artifact_build_and_observation_projections() -> None:
    dashboard = Path("frontend/src/pages/ProjectDashboardPage.tsx").read_text(
        encoding="utf-8"
    )
    client = Path("frontend/src/api/client.ts").read_text(encoding="utf-8")
    components = {
        path.name
        for path in Path("frontend/src/components").glob("*.tsx")
    }

    assert {"ArtifactViewer.tsx", "BuildPanel.tsx", "ObservationTimeline.tsx"} <= components
    assert "ArtifactViewer" in dashboard
    assert "BuildPanel" in dashboard
    assert "ObservationTimeline" in dashboard
    assert '"/api/firmware/generate"' in client
    assert '"/api/build/start"' in client
    assert "dangerouslySetInnerHTML" not in dashboard
