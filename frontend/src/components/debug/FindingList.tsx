import type { DebugFinding } from "../../types/debug";

export function FindingList({ findings }: { findings: DebugFinding[] }) {
  return <div className="review-list">{findings.map((finding) => <article key={finding.finding_id}><div className="panel-heading"><strong>{finding.category}</strong><span>{finding.severity}</span></div><p>{finding.summary}</p><p className="muted">Status: {finding.status} / Evidence: {finding.evidence_reference}</p></article>)}</div>;
}
