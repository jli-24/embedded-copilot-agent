import type { ModelRuntimeStatus } from "../../types/runtime";

export function ModelRuntimePanel({ status, error, loading }: { status: ModelRuntimeStatus | null; error: string | null; loading: boolean }) {
  return <section className="panel compact-panel"><div className="panel-heading"><h2>Model Runtime</h2><span className="status-pill status-pending">Read-only</span></div>
    {loading && <p className="muted">Checking runtime status...</p>}
    {!loading && error && <p className="muted">Model runtime is unavailable.</p>}
    {!loading && !error && status && <dl className="runtime-details"><dt>Provider status</dt><dd>{status.status}</dd><dt>Generation status</dt><dd>{status.provider === "unavailable" ? "Unavailable" : "Available"}</dd></dl>}
  </section>;
}
