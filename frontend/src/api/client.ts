import type {
  AttachmentProjection,
  ConversationFeedbackProjection,
  DashboardProjection,
  EngineeringChatResponse,
  FeedbackType,
  ProjectReference,
  ReportProjection,
  TimelineProjection,
} from "../types/contracts";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new ApiError(response.status, "The engineering service is unavailable.");
  }
  return (await response.json()) as T;
}

export const api = {
  createProject: (requirement: string) =>
    request<ProjectReference>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ requirement }),
    }),
  dashboard: (projectId: string) =>
    request<DashboardProjection>(`/api/projects/${projectId}/dashboard`),
  timeline: (projectId: string) =>
    request<TimelineProjection>(`/api/projects/${projectId}/timeline`),
  report: (projectId: string) =>
    request<ReportProjection>(`/api/projects/${projectId}/report`),
  attachment: (
    projectId: string,
    metadata: Record<string, string | number>,
  ) =>
    request<AttachmentProjection>(`/api/projects/${projectId}/attachments`, {
      method: "POST",
      body: JSON.stringify(metadata),
    }),
  chat: (projectId: string, message: string) =>
    request<EngineeringChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        request_id: `chat-${projectId}`,
        project_id: projectId,
        message,
        requested_at: new Date().toISOString(),
      }),
    }),
  feedback: (projectId: string, feedbackType: FeedbackType, message: string) =>
    request<ConversationFeedbackProjection>("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        feedback_id: `feedback-${projectId}-${feedbackType.toLowerCase()}`,
        project_id: projectId,
        target_agent: "ENGINEERING_CHAT",
        feedback_type: feedbackType,
        message,
        timestamp: new Date().toISOString(),
      }),
    }),
};
