import type { RepairProposal } from "../../types/autonomous";
export function RepairProposalPanel({ proposal }: { proposal: RepairProposal | null }) {
  return <section className="panel"><div className="panel-heading"><h2>Repair Proposal</h2><span className="status-pill status-review_required">Review only</span></div>{proposal ? <div className="proposal-block"><strong>{proposal.issue_summary}</strong><span>Area: {proposal.affected_area}</span><span>Suggested change: {proposal.suggested_change}</span><span>Evidence: {proposal.evidence_reference}</span></div> : <p className="muted">No repair proposal is available.</p>}</section>;
}
