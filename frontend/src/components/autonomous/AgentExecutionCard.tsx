import type { AgentExecutionView } from "../../types/autonomous";

export function AgentExecutionCard({ agent }: { agent: AgentExecutionView }) {
  return <article className="agent-card"><div><strong>{agent.agent_id}</strong><span>{agent.task_id}</span></div>
    <span className={`status-pill status-${agent.status.toLowerCase()}`}>{agent.status}</span>
    {agent.summary && <p>{agent.summary}</p>}
  </article>;
}
