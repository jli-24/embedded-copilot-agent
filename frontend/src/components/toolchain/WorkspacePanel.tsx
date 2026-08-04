import type { WorkspaceSnapshot } from "../../types/workspace";
export function WorkspacePanel({ snapshot, error, loading }: { snapshot: WorkspaceSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Workspace Projection</h2><span className="status-pill status-pending">Read-only</span></div>
    {loading && <p className="muted">Loading workspace projection...</p>}
    {!loading && error && <p className="muted">Workspace projection is unavailable.</p>}
    {!loading && !error && snapshot && <><p className="muted">Status: {snapshot.status}</p><div className="proposal-list">{snapshot.artifacts.map((artifact) => <div className="proposal-block" key={artifact.artifact_id}><strong>{artifact.artifact_type}</strong><span>Approval: {artifact.status}</span><span>Files: {artifact.filenames.join(", ")}</span></div>)}</div></>}
  </section>;
}
