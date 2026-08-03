from __future__ import annotations

from .contracts import MarkdownArtifact


def render_markdown(artifact: MarkdownArtifact) -> str:
    lines = [
        f"# {artifact.title}",
        "",
        f"- Type: `{artifact.memory_type.value}`",
        f"- Status: `{artifact.status}`",
        f"- Layer: `{artifact.layer}`",
        f"- Tags: {', '.join(artifact.tags) if artifact.tags else 'none'}",
        "",
        "## Summary",
        "",
        artifact.summary,
        "",
        "## Evidence References",
        "",
    ]
    lines.extend(f"- `{reference}`" for reference in artifact.evidence_references)
    if not artifact.evidence_references:
        lines.append("- none")
    return "\n".join(lines) + "\n"

