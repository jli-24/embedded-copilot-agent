import type { AutonomousLoopSnapshot } from "../types/autonomous";

export type AutonomousApiError =
  | "AUTONOMOUS_PROJECT_NOT_FOUND"
  | "AUTONOMOUS_SNAPSHOT_REJECTED"
  | "AUTONOMOUS_UNAVAILABLE";

export class AutonomousRequestError extends Error {
  readonly code: AutonomousApiError;
  constructor(code: AutonomousApiError) {
    super(code);
    this.name = "AutonomousRequestError";
    this.code = code;
  }
}

export function validateProjectId(projectId: string): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(projectId)) {
    throw new AutonomousRequestError("AUTONOMOUS_SNAPSHOT_REJECTED");
  }
  return projectId;
}

export async function fetchAutonomousLoop(
  projectId: string,
  fetcher: typeof fetch = fetch,
): Promise<AutonomousLoopSnapshot> {
  const safeProjectId = validateProjectId(projectId);
  let response: Response;
  try {
    response = await fetcher(`/api/autonomous/loop/${encodeURIComponent(safeProjectId)}`);
  } catch {
    throw new AutonomousRequestError("AUTONOMOUS_UNAVAILABLE");
  }
  if (response.ok) {
    try {
      return (await response.json()) as AutonomousLoopSnapshot;
    } catch {
      throw new AutonomousRequestError("AUTONOMOUS_SNAPSHOT_REJECTED");
    }
  }
  const code: AutonomousApiError = response.status === 404
    ? "AUTONOMOUS_PROJECT_NOT_FOUND"
    : response.status === 422
      ? "AUTONOMOUS_SNAPSHOT_REJECTED"
      : "AUTONOMOUS_UNAVAILABLE";
  throw new AutonomousRequestError(code);
}
