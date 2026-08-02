export type StageName =
  | "REQUIREMENT"
  | "ARCHITECTURE"
  | "HARDWARE"
  | "FIRMWARE"
  | "VALIDATION"
  | "ARTIFACT"
  | "EXECUTION"
  | "FEEDBACK"
  | "OPTIMIZATION";

export type StageStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";

export interface ProjectReference {
  project_id: string;
  project_name: string;
  current_stage: StageName;
  workspace_fingerprint: string;
  fingerprint: string;
}

export interface StageProjection {
  stage: StageName;
  status: StageStatus;
  reference_ids: string[];
  fingerprint: string;
}

export interface DashboardProjection {
  project_id: string;
  project_name: string;
  current_stage: StageName;
  overall_progress: number;
  stages: StageProjection[];
  fingerprint: string;
}

export interface TimelineEvent {
  event: string;
  reference_id: string;
  reference_type: string;
  timestamp: string;
  source_fingerprint: string;
  fingerprint: string;
}

export interface TimelineProjection {
  project_id: string;
  events: TimelineEvent[];
  fingerprint: string;
}

export interface ReportSection {
  stage: StageName;
  status: StageStatus;
  reference_ids: string[];
  source_fingerprints: string[];
  fingerprint: string;
}

export interface ReportProjection {
  project_id: string;
  project_name: string;
  project_summary: string;
  sections: ReportSection[];
  decision_ids: string[];
  review: {
    pending_reviews: number;
    approved: number;
    rejected: number;
    change_requests: number;
    reference_ids: string[];
  };
  generated_at: string;
  source_fingerprint: string;
  fingerprint: string;
}

export interface AttachmentProjection {
  project_id: string;
  session_id: string;
  reference_id: string;
  attachment_type: string;
  basename: string;
  summary: string;
  size_bytes: number;
  observed_at: string;
  source_fingerprint: string;
  fingerprint: string;
}

export type EngineeringEventType =
  | "PROJECT_STARTED"
  | "AGENT_STARTED"
  | "AGENT_PROGRESS"
  | "ARTIFACT_CREATED"
  | "WARNING"
  | "ERROR"
  | "USER_REQUIRED"
  | "COMPLETED"
  | "USER_FEEDBACK";

export interface EngineeringEventProjection {
  sequence: number;
  event_type: EngineeringEventType;
  stage: string;
  status: string;
  count: number;
  reference_id?: string;
  timestamp: string;
  fingerprint: string;
}

export interface EngineeringChatResponse {
  request_id: string;
  project_id: string;
  requirement_analysis: string;
  architecture_recommendation: string;
  hardware_suggestion: string;
  risk_analysis: string;
  next_action: string;
  reference_ids: string[];
  events: EngineeringEventProjection[];
  fingerprint: string;
}

export type FeedbackType =
  | "ACCEPT"
  | "REJECT"
  | "MODIFY"
  | "QUESTION"
  | "CORRECT"
  | "APPROVE";

export interface ConversationFeedbackProjection {
  feedback_id: string;
  session_id: string;
  target_agent: string;
  feedback_type: FeedbackType;
  event: EngineeringEventProjection;
  fingerprint: string;
}
