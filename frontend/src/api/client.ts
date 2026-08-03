import type {
  AttachmentProjection,
  ConversationFeedbackProjection,
  DashboardProjection,
  EngineeringChatResponse,
  FeedbackType,
  FirmwareProposal,
  ProjectReference,
  ReportProjection,
  TimelineProjection,
  WebBuildResultProjection,
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
  generateFirmware: (projectId: string) =>
    request<FirmwareProposal>("/api/firmware/generate", {
      method: "POST",
      body: JSON.stringify({
        project_id: projectId,
        request_id: `firmware-${projectId}`,
        requested_at: new Date().toISOString(),
      }),
    }),
  startBuild: (proposal: FirmwareProposal) => {
    const timestamp = new Date().toISOString();
    return request<WebBuildResultProjection>("/api/build/start", {
      method: "POST",
      body: JSON.stringify({
        build_id: `build-${proposal.project_id}`,
        firmware_request_id: proposal.request_id,
        approval_reference_id: `approval-${proposal.project_id}`,
        requested_at: timestamp,
      }),
    });
  },
};
