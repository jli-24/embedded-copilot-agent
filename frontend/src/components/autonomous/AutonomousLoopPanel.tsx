import type { AutonomousLoopSnapshot } from "../../types/autonomous";
import { AgentExecutionCard } from "./AgentExecutionCard";
import { ApprovalGate } from "./ApprovalGate";
import { LoopTimeline } from "./LoopTimeline";
import { TaskGraph } from "./TaskGraph";
import { VerificationStatus } from "./VerificationStatus";

export function AutonomousLoopPanel({ snapshot }: { snapshot: AutonomousLoopSnapshot }) {
  return <main className="console-shell">
    <header className="loop-header"><div><p className="eyebrow">Autonomous Engineering Loop</p><h1>{snapshot.project_id}</h1></div>
      <div className="headline-status"><span className={`status-pill status-${snapshot.status.toLowerCase()}`}>{snapshot.status}</span><strong>{snapshot.progress}%</strong></div>
    </header>
    <section className="summary-grid"><div><span>Current task</span><strong>{snapshot.current_task ?? "None"}</strong></div><div><span>Next task</span><strong>{snapshot.next_task ?? "None"}</strong></div><div><span>Updated</span><strong>{new Date(snapshot.updated_at).toLocaleString()}</strong></div></section>
    <section className="panel"><div className="panel-heading"><h2>Loop Timeline</h2><span>{snapshot.timeline.length} stages</span></div><LoopTimeline items={snapshot.timeline} /></section>
    <div className="two-column"><TaskGraph graph={snapshot.task_graph} /><div className="panel"><div className="panel-heading"><h2>Agent Execution</h2><span>{snapshot.agents.length}</span></div><div className="agent-list">{snapshot.agents.length ? snapshot.agents.map((agent) => <AgentExecutionCard key={`${agent.agent_id}-${agent.task_id}`} agent={agent} />) : <p className="muted">No agent activity available.</p>}</div></div></div>
    <div className="two-column"><ApprovalGate approval={snapshot.approval} /><VerificationStatus verification={snapshot.verification} repair={snapshot.repair} /></div>
  </main>;
}
