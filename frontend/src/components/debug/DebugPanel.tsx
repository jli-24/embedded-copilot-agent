import type { DebugAnalysisSnapshot } from "../../types/debug";
import { FindingList } from "./FindingList";

export function DebugPanel({ snapshot, error, loading }: { snapshot: DebugAnalysisSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Debug analysis</h2><span className="status-pill status-running">DEBUGGING</span></div>{loading && <p className="muted">Loading debug findings...</p>}{!loading && error && <p className="muted">Debug analysis is unavailable.</p>}{!loading && !error && snapshot && <><p>Failure: {snapshot.failure_reference}</p><FindingList findings={snapshot.findings} /></>}</section>;
}
