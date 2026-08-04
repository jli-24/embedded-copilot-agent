import type { GenerationArtifact } from "../../types/generation";

export function ArtifactList({ artifacts, onSelect }: { artifacts: GenerationArtifact[]; onSelect: (artifact: GenerationArtifact) => void }) {
  return <div className="artifact-list" role="list">{artifacts.map((artifact) => <button className="artifact-item" key={artifact.artifact_id} type="button" onClick={() => onSelect(artifact)}>
    <span><strong>{artifact.artifact_type}</strong><small>{artifact.artifact_id}</small></span><span className="status-pill status-review_required">Review</span>
  </button>)}</div>;
}
