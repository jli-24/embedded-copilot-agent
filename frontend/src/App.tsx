import { useState } from "react";
import { AutonomousRequestError, fetchAutonomousLoop } from "./api/autonomous";
import { AutonomousLoopPanel } from "./components/autonomous/AutonomousLoopPanel";
import type { AutonomousLoopSnapshot } from "./types/autonomous";
import { fetchGeneration, GenerationRequestError } from "./api/generation";
import { GenerationPanel } from "./components/generation/GenerationPanel";
import type { GenerationSnapshot } from "./types/generation";
import { fetchRuntimeStatus, RuntimeRequestError } from "./api/runtime";
import { fetchWorkspace, WorkspaceRequestError } from "./api/workspace";
import { fetchToolchain, ToolchainRequestError } from "./api/toolchain";
import { fetchComponents, ComponentRequestError } from "./api/components";
import type { ModelRuntimeStatus } from "./types/runtime";
import type { WorkspaceSnapshot } from "./types/workspace";
import type { ToolchainSnapshot } from "./types/toolchain";
import type { ComponentRecommendation } from "./types/components";
import { ModelRuntimePanel } from "./components/runtime/ModelRuntimePanel";
import { WorkspacePanel } from "./components/toolchain/WorkspacePanel";
import { BuildPanel } from "./components/toolchain/BuildPanel";
import { ComponentRecommendationPanel } from "./components/components/ComponentRecommendationPanel";

export default function App() {
  const [projectId, setProjectId] = useState("");
  const [snapshot, setSnapshot] = useState<AutonomousLoopSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [generation, setGeneration] = useState<GenerationSnapshot | null>(null);
  const [generationError, setGenerationError] = useState<GenerationRequestError["code"] | null>(null);
  const [generationLoading, setGenerationLoading] = useState(false);
  const [runtime, setRuntime] = useState<ModelRuntimeStatus | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceSnapshot | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [toolchain, setToolchain] = useState<ToolchainSnapshot | null>(null);
  const [toolchainError, setToolchainError] = useState<string | null>(null);
  const [components, setComponents] = useState<ComponentRecommendation[] | null>(null);
  const [componentsError, setComponentsError] = useState<string | null>(null);
  const [resourceLoading, setResourceLoading] = useState(false);
  async function load() {
    setLoading(true); setError(null); setSnapshot(null); setGeneration(null); setGenerationError(null); setGenerationLoading(false);
    setRuntime(null); setRuntimeError(null); setWorkspace(null); setWorkspaceError(null); setToolchain(null); setToolchainError(null); setComponents(null); setComponentsError(null);
    try {
      const loop = await fetchAutonomousLoop(projectId);
      setSnapshot(loop); setResourceLoading(true); setGenerationLoading(true);
      const results = await Promise.allSettled([
        fetchGeneration(projectId), fetchRuntimeStatus(), fetchWorkspace(projectId), fetchToolchain(projectId), fetchComponents(projectId),
      ]);
      const [generationResult, runtimeResult, workspaceResult, toolchainResult, componentsResult] = results;
      if (generationResult.status === "fulfilled") setGeneration(generationResult.value);
      else setGenerationError(generationResult.reason instanceof GenerationRequestError ? generationResult.reason.code : "GENERATION_UNAVAILABLE");
      if (runtimeResult.status === "fulfilled") setRuntime(runtimeResult.value);
      else setRuntimeError(runtimeResult.reason instanceof RuntimeRequestError ? runtimeResult.reason.code : "MODEL_UNAVAILABLE");
      if (workspaceResult.status === "fulfilled") setWorkspace(workspaceResult.value);
      else setWorkspaceError(workspaceResult.reason instanceof WorkspaceRequestError ? workspaceResult.reason.code : "WORKSPACE_UNAVAILABLE");
      if (toolchainResult.status === "fulfilled") setToolchain(toolchainResult.value);
      else setToolchainError(toolchainResult.reason instanceof ToolchainRequestError ? toolchainResult.reason.code : "TOOLCHAIN_UNAVAILABLE");
      if (componentsResult.status === "fulfilled") setComponents(componentsResult.value);
      else setComponentsError(componentsResult.reason instanceof ComponentRequestError ? componentsResult.reason.code : "COMPONENT_UNAVAILABLE");
    }
    catch (reason) {
      setError(reason instanceof AutonomousRequestError ? reason.code : "AUTONOMOUS_UNAVAILABLE");
    } finally { setLoading(false); setGenerationLoading(false); setResourceLoading(false); }
  }
  return <div className="app"><section className="load-bar"><div><p className="eyebrow">Embedded Copilot v1.6</p><h1>Engineering Console</h1></div><form onSubmit={(event) => { event.preventDefault(); void load(); }}><label htmlFor="project-id">Project ID</label><div className="load-controls"><input id="project-id" value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="camera-project" maxLength={96} /><button type="submit" disabled={loading || !projectId.trim()}>{loading ? "Loading..." : "Load snapshot"}</button></div></form></section>
    {error && <section className="safe-state" role="alert"><h2>{error}</h2><p>The autonomous loop snapshot is not available.</p></section>}
    {!error && snapshot && <><AutonomousLoopPanel snapshot={snapshot} /><GenerationPanel snapshot={generation} error={generationError} loading={generationLoading} /><div className="two-column"><ModelRuntimePanel status={runtime} error={runtimeError} loading={resourceLoading} /><WorkspacePanel snapshot={workspace} error={workspaceError} loading={resourceLoading} /><BuildPanel snapshot={toolchain} error={toolchainError} loading={resourceLoading} /></div><ComponentRecommendationPanel items={components} error={componentsError} loading={resourceLoading} /></>}
    {!error && !snapshot && !loading && <section className="empty-state"><h2>Choose a project</h2><p>Load a verified, read-only loop snapshot to inspect its current state.</p></section>}
  </div>;
}
