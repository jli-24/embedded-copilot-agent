from __future__ import annotations

from pathlib import Path


def test_dockerfile_contains_api_and_web_runtime_assets() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.11-slim")
    assert "COPY src ./src" in dockerfile
    assert "COPY web ./web" in dockerfile
    assert "COPY demo ./demo" in dockerfile
    assert "EXPOSE 8000 8501" in dockerfile
    assert "embedded_copilot.api.main:app" in dockerfile


def test_compose_keeps_api_health_and_web_client_boundary() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "  api:" in compose
    assert "  web:" in compose
    assert "embedded_copilot.api.main:app" in compose
    assert "streamlit" in compose and "web/app.py" in compose
    assert "http://127.0.0.1:8000/health" in compose
    assert "EMBEDDED_COPILOT_API_URL: http://api:8000" in compose
    assert '"8000:8000"' in compose
    assert '"8501:8501"' in compose
