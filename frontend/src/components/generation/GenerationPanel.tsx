import { useState } from "react";
import type { GenerationRequestError } from "../../api/generation";
import type { GenerationArtifact, GenerationSnapshot } from "../../types/generation";
import { ArtifactList } from "./ArtifactList";
import { FirmwareArtifactViewer } from "./FirmwareArtifactViewer";
import { HardwareArtifactViewer } from "./HardwareArtifactViewer";

export function GenerationPanel({ snapshot, error, loading }: { snapshot: GenerationSnapshot | null; error: GenerationRequestError["code"] | null; loading: boolean }) {
  const [selected, setSelected] = useState<GenerationArtifact | null>(null);
  if (loading) return <section className="panel generation-panel"><div className="panel-heading"><h2>Engineering Generation</h2></div><p className="muted">Loading artifact projection...</p></section>;
  if (error) return <section className="panel generation-panel safe-inline"><div className="panel-heading"><h2>Engineering Generation</h2><span className="status-pill status-failed">Unavailable</span></div><p className="muted">The artifact projection is not available.</p></section>;
  if (!snapshot) return null;
  const active = selected ?? snapshot.artifacts[0] ?? null;
  return <section className="panel generation-panel"><div className="panel-heading"><h2>Engineering Generation</h2><span className="status-pill status-review_required">{snapshot.status}</span></div>
    {snapshot.artifacts.length === 0 ? <p className="muted">No artifact proposals are available.</p> : <div className="artifact-layout"><ArtifactList artifacts={snapshot.artifacts} onSelect={setSelected} />{active && (active.artifact_type === "FIRMWARE" ? <FirmwareArtifactViewer artifact={active} /> : <HardwareArtifactViewer artifact={active} />)}</div>}
  </section>;
}
