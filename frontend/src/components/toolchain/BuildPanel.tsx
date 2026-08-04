import type { ToolchainSnapshot } from "../../types/toolchain";
export function BuildPanel({ snapshot, error, loading }: { snapshot: ToolchainSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Build</h2><span className="status-pill status-pending">Read-only</span></div>
    {loading && <p className="muted">Loading build status...</p>}
    {!loading && error && <p className="muted">Toolchain status is unavailable.</p>}
    {!loading && !error && snapshot && <dl className="runtime-details"><dt>Build</dt><dd>{snapshot.build_status}</dd><dt>Workspace</dt><dd>{snapshot.workspace_status}</dd><dt>Artifact</dt><dd>{snapshot.artifact?.reference_id ?? "None"}</dd></dl>}
  </section>;
}
