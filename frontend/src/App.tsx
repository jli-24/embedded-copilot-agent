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
import { fetchDevice, DeviceRequestError } from "./api/device";
import { fetchObservation, ObservationRequestError } from "./api/observation";
import { fetchValidationLoop, ValidationRequestError } from "./api/validation";
import type { DeviceSnapshot } from "./types/device";
import type { ObservationSnapshot } from "./types/observation";
import type { ValidationSnapshot } from "./types/validation";
import { DevicePanel } from "./components/validation/DevicePanel";
import { FlashPanel } from "./components/validation/FlashPanel";
import { ObservationPanel } from "./components/validation/ObservationPanel";
import { ValidationLoopPanel } from "./components/validation/ValidationLoopPanel";

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
  const [device, setDevice] = useState<DeviceSnapshot | null>(null);
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const [observation, setObservation] = useState<ObservationSnapshot | null>(null);
  const [observationError, setObservationError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationSnapshot | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  async function load() {
    setLoading(true); setError(null); setSnapshot(null); setGeneration(null); setGenerationError(null); setGenerationLoading(false);
    setRuntime(null); setRuntimeError(null); setWorkspace(null); setWorkspaceError(null); setToolchain(null); setToolchainError(null); setComponents(null); setComponentsError(null);
    setDevice(null); setDeviceError(null); setObservation(null); setObservationError(null); setValidation(null); setValidationError(null);
    try {
      const loop = await fetchAutonomousLoop(projectId);
      setSnapshot(loop); setResourceLoading(true); setGenerationLoading(true);
      const results = await Promise.allSettled([
        fetchGeneration(projectId), fetchRuntimeStatus(), fetchWorkspace(projectId), fetchToolchain(projectId), fetchComponents(projectId), fetchDevice(projectId), fetchObservation(projectId), fetchValidationLoop(projectId),
      ]);
      const [generationResult, runtimeResult, workspaceResult, toolchainResult, componentsResult, deviceResult, observationResult, validationResult] = results;
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
      if (deviceResult.status === "fulfilled") setDevice(deviceResult.value);
      else setDeviceError(deviceResult.reason instanceof DeviceRequestError ? deviceResult.reason.code : "DEVICE_UNAVAILABLE");
      if (observationResult.status === "fulfilled") setObservation(observationResult.value);
      else setObservationError(observationResult.reason instanceof ObservationRequestError ? observationResult.reason.code : "OBSERVATION_UNAVAILABLE");
      if (validationResult.status === "fulfilled") setValidation(validationResult.value);
      else setValidationError(validationResult.reason instanceof ValidationRequestError ? validationResult.reason.code : "VALIDATION_UNAVAILABLE");
    }
    catch (reason) {
      setError(reason instanceof AutonomousRequestError ? reason.code : "AUTONOMOUS_UNAVAILABLE");
    } finally { setLoading(false); setGenerationLoading(false); setResourceLoading(false); }
  }
  return <div className="app"><section className="load-bar"><div><p className="eyebrow">Embedded Copilot v1.6</p><h1>Engineering Console</h1></div><form onSubmit={(event) => { event.preventDefault(); void load(); }}><label htmlFor="project-id">Project ID</label><div className="load-controls"><input id="project-id" value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="camera-project" maxLength={96} /><button type="submit" disabled={loading || !projectId.trim()}>{loading ? "Loading..." : "Load snapshot"}</button></div></form></section>
    {error && <section className="safe-state" role="alert"><h2>{error}</h2><p>The autonomous loop snapshot is not available.</p></section>}
    {!error && snapshot && <><AutonomousLoopPanel snapshot={snapshot} /><GenerationPanel snapshot={generation} error={generationError} loading={generationLoading} /><div className="two-column"><ModelRuntimePanel status={runtime} error={runtimeError} loading={resourceLoading} /><WorkspacePanel snapshot={workspace} error={workspaceError} loading={resourceLoading} /><BuildPanel snapshot={toolchain} error={toolchainError} loading={resourceLoading} /><DevicePanel snapshot={device} error={deviceError} loading={resourceLoading} /><FlashPanel error={null} loading={resourceLoading} /><ObservationPanel snapshot={observation} error={observationError} loading={resourceLoading} /></div><ValidationLoopPanel snapshot={validation} error={validationError} loading={resourceLoading} /><ComponentRecommendationPanel items={components} error={componentsError} loading={resourceLoading} /></>}
    {!error && !snapshot && !loading && <section className="empty-state"><h2>Choose a project</h2><p>Load a verified, read-only loop snapshot to inspect its current state.</p></section>}
  </div>;
}
