import type { AutonomousLoopSnapshotV20 } from "../../types/autonomousV20";
export function ApprovalPanel({ snapshot, onApprove, onReject }: { snapshot: AutonomousLoopSnapshotV20; onApprove?: () => void; onReject?: () => void }) {
  const action = snapshot.pending_action;
  return <section className="panel"><div className="panel-heading"><h2>Approval Gate</h2><span className={`status-pill status-${snapshot.approval_status.toLowerCase()}`}>{snapshot.approval_status}</span></div>{action ? <><p className="muted">Pending action: {action.action_type}</p><div className="load-controls">{onApprove && <button type="button" onClick={onApprove}>Approve</button>}{onReject && <button type="button" onClick={onReject}>Reject</button>}</div></> : <p className="muted">No action is waiting for approval.</p>}</section>;
}
