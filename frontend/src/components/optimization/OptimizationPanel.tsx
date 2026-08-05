import type { OptimizationProposal } from "../../types/optimization";
import { ProposalCard } from "./ProposalCard";

export function OptimizationPanel({ proposal, error, loading, onApprove, onReject }: { proposal: OptimizationProposal | null; error: string | null; loading: boolean; onApprove?: () => void; onReject?: () => void }) {
  return <section className="panel"><div className="panel-heading"><h2>Optimization review</h2><span className="status-pill status-review_required">OPTIMIZATION_REVIEW</span></div>{loading && <p className="muted">Loading optimization proposal...</p>}{!loading && error && <p className="muted">Optimization proposal is unavailable.</p>}{!loading && !error && proposal && <ProposalCard proposal={proposal} onApprove={onApprove} onReject={onReject} />}</section>;
}
