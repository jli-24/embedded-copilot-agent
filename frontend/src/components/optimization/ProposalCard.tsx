import type { OptimizationProposal } from "../../types/optimization";

export function ProposalCard({ proposal, onApprove, onReject }: { proposal: OptimizationProposal; onApprove?: () => void; onReject?: () => void }) {
  return <article className="proposal-block"><div className="panel-heading"><strong>{proposal.target_area}</strong><span>{proposal.status}</span></div><p>{proposal.suggested_change}</p><p>{proposal.reason}</p><p className="muted">Risk: {proposal.risk} / Confidence: {proposal.confidence} / Evidence: {proposal.evidence_reference}</p>{proposal.status === "PROPOSED" && <div className="load-controls"><button type="button" onClick={onApprove}>Approve</button><button type="button" onClick={onReject}>Reject</button></div>}</article>;
}
