import type { AutonomousLoopSnapshotV20 } from "../types/autonomousV20";

export type AutonomousV20Error = "AUTONOMOUS_UNAVAILABLE" | "LOOP_NOT_FOUND" | "ACTION_APPROVAL_REQUIRED" | "INVALID_TRANSITION" | "LOOP_REJECTED" | "APPROVAL_EXPIRED" | "AUTONOMOUS_SNAPSHOT_REJECTED";
export class AutonomousV20RequestError extends Error { readonly code: AutonomousV20Error; constructor(code: AutonomousV20Error) { super(code); this.code = code; } }
const safeProject = (value: string) => /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(value);
const responseCode = async (response: Response, fallback: AutonomousV20Error): Promise<AutonomousV20Error> => {
  try { const body = await response.json(); const code = body?.error; if (typeof code === "string") return code as AutonomousV20Error; } catch { /* fixed fallback */ }
  return fallback;
};
export async function fetchAutonomousV20(projectId: string, fetcher: typeof fetch = fetch): Promise<AutonomousLoopSnapshotV20> {
  if (!safeProject(projectId)) throw new AutonomousV20RequestError("AUTONOMOUS_SNAPSHOT_REJECTED");
  let response: Response; try { response = await fetcher(`/api/v2/autonomous/loop/${encodeURIComponent(projectId)}`); } catch { throw new AutonomousV20RequestError("AUTONOMOUS_UNAVAILABLE"); }
  if (response.ok) { try { return (await response.json()) as AutonomousLoopSnapshotV20; } catch { throw new AutonomousV20RequestError("AUTONOMOUS_SNAPSHOT_REJECTED"); } }
  throw new AutonomousV20RequestError(await responseCode(response, response.status === 404 ? "LOOP_NOT_FOUND" : "AUTONOMOUS_UNAVAILABLE"));
}
async function decide(actionId: string, route: "approve" | "reject", body: object, fetcher: typeof fetch): Promise<AutonomousLoopSnapshotV20> {
  let response: Response; try { response = await fetcher(`/api/autonomous/action/${encodeURIComponent(actionId)}/${route}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); } catch { throw new AutonomousV20RequestError("AUTONOMOUS_UNAVAILABLE"); }
  if (response.ok) return (await response.json()) as AutonomousLoopSnapshotV20;
  throw new AutonomousV20RequestError(await responseCode(response, response.status === 503 ? "AUTONOMOUS_UNAVAILABLE" : "LOOP_REJECTED"));
}
export function approveAutonomousAction(actionId: string, body: object, fetcher: typeof fetch = fetch) { return decide(actionId, "approve", body, fetcher); }
export function rejectAutonomousAction(actionId: string, body: object, fetcher: typeof fetch = fetch) { return decide(actionId, "reject", body, fetcher); }
