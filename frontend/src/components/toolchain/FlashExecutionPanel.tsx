import type { ToolExecutionResult } from "../../types/toolAdapter";

export function FlashExecutionPanel({ result, error, loading }: { result: ToolExecutionResult | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Adapter flash</h2><span className="status-pill status-pending">Approval-bound</span></div>
    {loading && <p className="muted">Loading flash projection...</p>}
    {!loading && error && <p className="muted">Flash projection is unavailable.</p>}
    {!loading && !error && result && <dl className="runtime-details"><dt>Status</dt><dd>{result.status}</dd><dt>Tool</dt><dd>{result.tool_type}</dd><dt>Summary</dt><dd>{result.summary}</dd></dl>}
    {!loading && !error && !result && <p className="muted">No flash execution result is available.</p>}
  </section>;
}
