export type LoopStage = "INITIALIZING" | "PLANNING" | "GENERATING" | "BUILDING" | "VALIDATING" | "ANALYZING" | "WAITING_APPROVAL" | "COMPLETED" | "FAILED";
export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";
export type LoopTimelineItemV20 = { stage: LoopStage; status: string; label: string; summary?: string | null };
export type PendingAction = { action_id: string; loop_id: string; action_type: string; action_fingerprint: string; approval_status: ApprovalStatus };
export type AutonomousLoopSnapshotV20 = { project_id: string; loop_id: string; current_stage: LoopStage; completed_stages: LoopStage[]; pending_action: PendingAction | null; approval_status: ApprovalStatus; iteration: number; timeline: LoopTimelineItemV20[]; fingerprint: string };
