import type { OptimizationAnalysis } from "../../types/optimizationV26";
import { OptimizationFindingCard } from "./OptimizationFindingCard";

export function OptimizationAnalysisPanel({ analysis, error, loading }: { analysis: OptimizationAnalysis | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Engineering optimization analysis</h2><span className="status-pill status-pending">Projection</span></div>{loading && <p className="muted">Loading optimization analysis...</p>}{!loading && error && <p className="muted">Optimization analysis is unavailable.</p>}{!loading && !error && analysis && <div className="review-list">{analysis.findings.map((finding) => <OptimizationFindingCard key={finding.finding_id} finding={finding} />)}</div>}</section>;
}
