import type { TaskGraph as TaskGraphModel } from "../../types/autonomous";

export function TaskGraph({ graph }: { graph: TaskGraphModel }) {
  return <section className="panel" aria-labelledby="task-graph-title">
    <div className="panel-heading"><h2 id="task-graph-title">Task Graph</h2><span>{graph.nodes.length} nodes</span></div>
    <div className="task-graph">{graph.nodes.map((node) => <div className={`graph-node status-${node.status.toLowerCase()}`} key={node.node_id}>
      <strong>{node.label}</strong><span>{node.status}</span>
    </div>)}</div>
    {graph.edges.length > 0 && <p className="graph-edges">{graph.edges.map((edge) => `${edge.source} → ${edge.target}`).join(" · ")}</p>}
  </section>;
}
