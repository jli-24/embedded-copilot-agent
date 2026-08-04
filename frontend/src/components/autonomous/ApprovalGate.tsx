import type { ApprovalGateView } from "../../types/autonomous";

export function ApprovalGate({ approval }: { approval: ApprovalGateView }) {
  return <section className="panel compact-panel" aria-labelledby="approval-title">
    <div className="panel-heading"><h2 id="approval-title">Approval</h2><span className={`status-pill status-${approval.status.toLowerCase()}`}>{approval.status}</span></div>
    {approval.reviewer && <p className="muted">Reviewed by {approval.reviewer}</p>}
  </section>;
}
