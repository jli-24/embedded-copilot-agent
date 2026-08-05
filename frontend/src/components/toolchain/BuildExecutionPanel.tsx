import type { ToolExecutionResult } from "../../types/toolAdapter";

export function BuildExecutionPanel({ result, error, loading }: { result: ToolExecutionResult | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Adapter build</h2><span className="status-pill status-pending">Approval-bound</span></div>
    {loading && <p className="muted">Loading build projection...</p>}
    {!loading && error && <p className="muted">Build projection is unavailable.</p>}
    {!loading && !error && result && <dl className="runtime-details"><dt>Status</dt><dd>{result.status}</dd><dt>Tool</dt><dd>{result.tool_type}</dd><dt>Summary</dt><dd>{result.summary}</dd></dl>}
    {!loading && !error && !result && <p className="muted">No build execution result is available.</p>}
  </section>;
}
