import type { AutonomousLoopSnapshotV20 } from "../../types/autonomousV20";
export function LoopStagePanel({ snapshot }: { snapshot: AutonomousLoopSnapshotV20 }) {
  return <section className="panel"><div className="panel-heading"><h2>Workflow stage</h2><span className="status-pill status-running">{snapshot.current_stage}</span></div><dl className="runtime-details"><dt>Loop</dt><dd>{snapshot.loop_id}</dd><dt>Iteration</dt><dd>{snapshot.iteration}</dd><dt>Completed</dt><dd>{snapshot.completed_stages.length}</dd></dl></section>;
}
