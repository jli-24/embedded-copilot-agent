import type { ToolCapabilitySnapshot } from "../../types/toolAdapter";

export function ToolStatusPanel({ snapshot, error, loading }: { snapshot: ToolCapabilitySnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Tool capabilities</h2><span className="status-pill status-pending">Read-only</span></div>
    {loading && <p className="muted">Loading tool status...</p>}
    {!loading && error && <p className="muted">Tool status is unavailable.</p>}
    {!loading && !error && snapshot && <dl className="runtime-details"><dt>Tool</dt><dd>{snapshot.tool_name}</dd><dt>Version</dt><dd>{snapshot.version}</dd><dt>Status</dt><dd>{snapshot.status}</dd><dt>Capabilities</dt><dd>{snapshot.capabilities.join(", ") || "None"}</dd></dl>}
  </section>;
}
