export type LoopStatus =
  | "PENDING" | "PLANNING" | "APPROVAL" | "EXECUTING" | "BUILDING"
  | "VERIFYING" | "REPAIRING" | "COMPLETED" | "FAILED";
export type ViewStatus =
  | "PENDING" | "RUNNING" | "APPROVED" | "REJECTED" | "PASSED"
  | "FAILED" | "NOT_REQUIRED" | "COMPLETED";

export interface LoopTimelineItem {
  stage: string;
  status: ViewStatus;
  label: string;
  summary?: string | null;
}
export interface TaskGraphNode { node_id: string; label: string; status: ViewStatus; }
export interface TaskGraphEdge { source: string; target: string; }
export interface TaskGraph { nodes: TaskGraphNode[]; edges: TaskGraphEdge[]; }
export interface AgentExecutionView {
  agent_id: string; task_id: string; status: ViewStatus; summary?: string | null;
}
export interface ApprovalGateView { status: ViewStatus; reviewer?: string | null; }
export interface VerificationStatusView { status: ViewStatus; review_required: boolean; }
export interface RepairLoopView { status: ViewStatus; iteration: number; max_iterations: number; }
export interface AutonomousLoopSnapshot {
  project_id: string;
  status: LoopStatus;
  progress: number;
  tasks: string[];
  current_task?: string | null;
  next_task?: string | null;
  timeline: LoopTimelineItem[];
  task_graph: TaskGraph;
  agents: AgentExecutionView[];
  approval: ApprovalGateView;
  verification: VerificationStatusView;
  repair: RepairLoopView;
  updated_at: string;
  fingerprint: string;
}
