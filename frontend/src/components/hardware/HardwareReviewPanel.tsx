import type { HardwareReviewProposal } from "../../types/hardware";

export function HardwareReviewPanel({ findings, error, loading }: { findings: HardwareReviewProposal[] | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Hardware review</h2><span className="status-pill status-pending">Projection</span></div>{loading && <p className="muted">Loading review findings...</p>}{!loading && error && <p className="muted">Hardware review is unavailable.</p>}{!loading && !error && findings && <div className="review-list">{findings.map((finding) => <article key={finding.review_id}><div className="panel-heading"><strong>{finding.category}</strong><span>{finding.severity}</span></div><p>{finding.summary}</p><p className="muted">Status: {finding.status} · Evidence: {finding.evidence_reference}</p></article>)}</div>}</section>;
}
