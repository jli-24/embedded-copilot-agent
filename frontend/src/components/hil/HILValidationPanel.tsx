import type { HILValidationResult } from "../../types/hil";
import { TestResultPanel } from "./TestResultPanel";

export function HILValidationPanel({ result, error, loading }: { result: HILValidationResult | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>HIL validation</h2><span className="status-pill status-pending">Projection</span></div>{loading && <p className="muted">Loading validation result...</p>}{!loading && error && <p className="muted">HIL validation is unavailable.</p>}{!loading && !error && result && <><p>Overall status: {result.overall_status}</p><p className="muted">Evidence: {result.evidence_reference}</p><TestResultPanel cases={result.test_cases} /></>}</section>;
}
