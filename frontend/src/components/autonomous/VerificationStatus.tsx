import type { RepairLoopView, VerificationStatusView } from "../../types/autonomous";

export function VerificationStatus({ verification, repair }: { verification: VerificationStatusView; repair: RepairLoopView }) {
  return <section className="panel compact-panel" aria-labelledby="verification-title">
    <div className="panel-heading"><h2 id="verification-title">Verification</h2><span className={`status-pill status-${verification.status.toLowerCase()}`}>{verification.status}</span></div>
    <p className="muted">{verification.review_required ? "Review required" : "No review flag"}</p>
    <div className="repair-line"><span>Repair loop</span><strong>{repair.status}</strong><span>{repair.iteration}/{repair.max_iterations}</span></div>
  </section>;
}
