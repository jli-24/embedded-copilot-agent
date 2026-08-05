import type { OptimizationFinding } from "../../types/optimizationV26";

export function OptimizationFindingCard({ finding }: { finding: OptimizationFinding }) {
  return <article className="review-list"><div className="panel-heading"><strong>{finding.category}</strong><span>{finding.status}</span></div><p>{finding.suggested_direction}</p><p className="muted">Target: {finding.target} / Confidence: {finding.confidence}</p><p className="muted">Evidence: {finding.evidence_reference}</p></article>;
}
