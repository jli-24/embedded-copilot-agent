from __future__ import annotations

from .contracts import GraphMarkdownArtifact, MarkdownArtifact


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
        "## Decision",
        "",
        artifact.decision or "none",
        "",
        "## Reason",
        "",
        artifact.reason or "none",
        "",
        "## Evidence References",
        "",
    ]
    lines.extend(f"- `{reference}`" for reference in artifact.evidence_references)
    if not artifact.evidence_references:
        lines.append("- none")
    lines.extend(("", "## Related Links", ""))
    lines.extend(f"- `{reference}`" for reference in artifact.related_links)
    if not artifact.related_links:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def render_graph_markdown(artifact: GraphMarkdownArtifact) -> str:
    lines = [
        f"# {artifact.entity_name}",
        "",
        f"- Type: `{artifact.node_type.value}`",
        f"- Status: `{artifact.verification_status}`",
        f"- Confidence: `{artifact.confidence}`",
        f"- Source: `{artifact.source_reference}`",
        f"- Fingerprint: `{artifact.fingerprint}`",
        "",
        "## Summary",
        "",
        artifact.summary,
        "",
        "## Related Nodes",
        "",
    ]
    lines.extend(artifact.related_links or ("- none",))
    return "\n".join(lines) + "\n"
