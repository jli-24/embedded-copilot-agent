import type { DebugAnalysisSnapshot } from "../../types/debug";

export function FirmwareDebugPanel({ snapshot, error, loading }: { snapshot: DebugAnalysisSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Firmware debug</h2><span className="status-pill status-running">Projection</span></div>{loading && <p className="muted">Loading debug reference...</p>}{!loading && error && <p className="muted">Firmware debug is unavailable.</p>}{!loading && !error && snapshot && <><p>Failure: {snapshot.failure_reference}</p><p className="muted">Findings: {snapshot.findings.length}</p></>}</section>;
}
