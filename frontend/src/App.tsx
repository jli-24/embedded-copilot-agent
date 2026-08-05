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
import { fetchAutonomousV20, approveAutonomousAction, rejectAutonomousAction, AutonomousV20RequestError } from "./api/autonomousV20";
import type { AutonomousLoopSnapshotV20 } from "./types/autonomousV20";
import { LoopStagePanel } from "./components/autonomous/LoopStagePanel";
import { ApprovalPanel } from "./components/autonomous/ApprovalPanel";
import { RepairProposalPanel } from "./components/autonomous/RepairProposalPanel";
import { fetchToolCapability, fetchToolDevice, ToolAdapterRequestError } from "./api/toolAdapter";
import type { ObservationSnapshot as AdapterObservation, ToolCapabilitySnapshot } from "./types/toolAdapter";
import { ToolStatusPanel } from "./components/toolchain/ToolStatusPanel";
import { BuildExecutionPanel } from "./components/toolchain/BuildExecutionPanel";
import { FlashExecutionPanel } from "./components/toolchain/FlashExecutionPanel";
import { DeviceObservationPanel } from "./components/toolchain/DeviceObservationPanel";
import { fetchHardwareDesign, fetchHardwareReview, HardwareRequestError } from "./api/hardware";
import type { HardwareReviewProposal, UnifiedHardwareModel } from "./types/hardware";
import { HardwareDesignPanel } from "./components/hardware/HardwareDesignPanel";
import { HardwareReviewPanel } from "./components/hardware/HardwareReviewPanel";
import { fetchDebugAnalysis, DebugRequestError } from "./api/debug";
import { fetchOptimization, approveOptimization, rejectOptimization, OptimizationRequestError } from "./api/optimization";
import type { DebugAnalysisSnapshot } from "./types/debug";
import type { OptimizationProposal } from "./types/optimization";
import { DebugPanel } from "./components/debug/DebugPanel";
import { OptimizationPanel } from "./components/optimization/OptimizationPanel";

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
  const [v20Snapshot, setV20Snapshot] = useState<AutonomousLoopSnapshotV20 | null>(null);
  const [v20Error, setV20Error] = useState<string | null>(null);
  const [toolCapabilities, setToolCapabilities] = useState<ToolCapabilitySnapshot | null>(null);
  const [toolCapabilitiesError, setToolCapabilitiesError] = useState<string | null>(null);
  const [adapterObservation, setAdapterObservation] = useState<AdapterObservation | null>(null);
  const [adapterObservationError, setAdapterObservationError] = useState<string | null>(null);
  const [hardwareDesign, setHardwareDesign] = useState<UnifiedHardwareModel | null>(null);
  const [hardwareDesignError, setHardwareDesignError] = useState<string | null>(null);
  const [hardwareReview, setHardwareReview] = useState<HardwareReviewProposal[] | null>(null);
  const [hardwareReviewError, setHardwareReviewError] = useState<string | null>(null);
  const [debugSnapshot, setDebugSnapshot] = useState<DebugAnalysisSnapshot | null>(null);
  const [debugError, setDebugError] = useState<string | null>(null);
  const [optimization, setOptimization] = useState<OptimizationProposal | null>(null);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  async function load() {
    setLoading(true); setError(null); setSnapshot(null); setGeneration(null); setGenerationError(null); setGenerationLoading(false);
    setRuntime(null); setRuntimeError(null); setWorkspace(null); setWorkspaceError(null); setToolchain(null); setToolchainError(null); setComponents(null); setComponentsError(null);
    setDevice(null); setDeviceError(null); setObservation(null); setObservationError(null); setValidation(null); setValidationError(null);
    setV20Snapshot(null); setV20Error(null);
    setToolCapabilities(null); setToolCapabilitiesError(null); setAdapterObservation(null); setAdapterObservationError(null);
    setHardwareDesign(null); setHardwareDesignError(null); setHardwareReview(null); setHardwareReviewError(null);
    setDebugSnapshot(null); setDebugError(null); setOptimization(null); setOptimizationError(null);
    try {
      const loop = await fetchAutonomousLoop(projectId);
      setSnapshot(loop); setResourceLoading(true); setGenerationLoading(true);
      const results = await Promise.allSettled([
        fetchGeneration(projectId), fetchRuntimeStatus(), fetchWorkspace(projectId), fetchToolchain(projectId), fetchComponents(projectId), fetchDevice(projectId), fetchObservation(projectId), fetchValidationLoop(projectId), fetchAutonomousV20(projectId), fetchToolCapability(projectId), fetchToolDevice(projectId), fetchHardwareDesign(projectId), fetchHardwareReview(projectId), fetchDebugAnalysis(projectId), fetchOptimization(projectId),
      ]);
      const [generationResult, runtimeResult, workspaceResult, toolchainResult, componentsResult, deviceResult, observationResult, validationResult, v20Result, toolCapabilityResult, adapterObservationResult, hardwareDesignResult, hardwareReviewResult, debugResult, optimizationResult] = results;
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
      if (v20Result.status === "fulfilled") setV20Snapshot(v20Result.value);
      else setV20Error(v20Result.reason instanceof AutonomousV20RequestError ? v20Result.reason.code : "AUTONOMOUS_UNAVAILABLE");
      if (toolCapabilityResult.status === "fulfilled") setToolCapabilities(toolCapabilityResult.value);
      else setToolCapabilitiesError(toolCapabilityResult.reason instanceof ToolAdapterRequestError ? toolCapabilityResult.reason.code : "TOOL_UNAVAILABLE");
      if (adapterObservationResult.status === "fulfilled") setAdapterObservation(adapterObservationResult.value);
      else setAdapterObservationError(adapterObservationResult.reason instanceof ToolAdapterRequestError ? adapterObservationResult.reason.code : "OBSERVATION_UNAVAILABLE");
      if (hardwareDesignResult.status === "fulfilled") setHardwareDesign(hardwareDesignResult.value);
      else setHardwareDesignError(hardwareDesignResult.reason instanceof HardwareRequestError ? hardwareDesignResult.reason.code : "HARDWARE_UNAVAILABLE");
      if (hardwareReviewResult.status === "fulfilled") setHardwareReview(hardwareReviewResult.value);
      else setHardwareReviewError(hardwareReviewResult.reason instanceof HardwareRequestError ? hardwareReviewResult.reason.code : "REVIEW_UNAVAILABLE");
      if (debugResult.status === "fulfilled") setDebugSnapshot(debugResult.value);
      else setDebugError(debugResult.reason instanceof DebugRequestError ? debugResult.reason.code : "DEBUG_UNAVAILABLE");
      if (optimizationResult.status === "fulfilled") setOptimization(optimizationResult.value);
      else setOptimizationError(optimizationResult.reason instanceof OptimizationRequestError ? optimizationResult.reason.code : "OPTIMIZATION_UNAVAILABLE");
    }
    catch (reason) {
      setError(reason instanceof AutonomousRequestError ? reason.code : "AUTONOMOUS_UNAVAILABLE");
    } finally { setLoading(false); setGenerationLoading(false); setResourceLoading(false); }
  }
  return <div className="app"><section className="load-bar"><div><p className="eyebrow">Embedded Copilot v1.6</p><h1>Engineering Console</h1></div><form onSubmit={(event) => { event.preventDefault(); void load(); }}><label htmlFor="project-id">Project ID</label><div className="load-controls"><input id="project-id" value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="camera-project" maxLength={96} /><button type="submit" disabled={loading || !projectId.trim()}>{loading ? "Loading..." : "Load snapshot"}</button></div></form></section>
    {error && <section className="safe-state" role="alert"><h2>{error}</h2><p>The autonomous loop snapshot is not available.</p></section>}
    {!error && snapshot && <><AutonomousLoopPanel snapshot={snapshot} /><GenerationPanel snapshot={generation} error={generationError} loading={generationLoading} /><DebugPanel snapshot={debugSnapshot} error={debugError} loading={resourceLoading} /><OptimizationPanel proposal={optimization} error={optimizationError} loading={resourceLoading} onApprove={optimization ? () => { void approveOptimization(optimization).then(setOptimization).catch((reason) => setOptimizationError(reason instanceof OptimizationRequestError ? reason.code : "PROPOSAL_REJECTED")); } : undefined} onReject={optimization ? () => { void rejectOptimization(optimization).then(setOptimization).catch((reason) => setOptimizationError(reason instanceof OptimizationRequestError ? reason.code : "PROPOSAL_REJECTED")); } : undefined} /><div className="two-column"><ModelRuntimePanel status={runtime} error={runtimeError} loading={resourceLoading} /><WorkspacePanel snapshot={workspace} error={workspaceError} loading={resourceLoading} /><BuildPanel snapshot={toolchain} error={toolchainError} loading={resourceLoading} /><ToolStatusPanel snapshot={toolCapabilities} error={toolCapabilitiesError} loading={resourceLoading} /><BuildExecutionPanel result={null} error={null} loading={resourceLoading} /><FlashExecutionPanel result={null} error={null} loading={resourceLoading} /><DevicePanel snapshot={device} error={deviceError} loading={resourceLoading} /><DeviceObservationPanel snapshot={adapterObservation} error={adapterObservationError} loading={resourceLoading} /><FlashPanel error={null} loading={resourceLoading} /><ObservationPanel snapshot={observation} error={observationError} loading={resourceLoading} /></div><HardwareDesignPanel model={hardwareDesign} error={hardwareDesignError} loading={resourceLoading} /><HardwareReviewPanel findings={hardwareReview} error={hardwareReviewError} loading={resourceLoading} /><ValidationLoopPanel snapshot={validation} error={validationError} loading={resourceLoading} /><ComponentRecommendationPanel items={components} error={componentsError} loading={resourceLoading} />{v20Snapshot && <><LoopStagePanel snapshot={v20Snapshot} /><ApprovalPanel snapshot={v20Snapshot} onApprove={v20Snapshot.pending_action ? () => { void approveAutonomousAction(v20Snapshot.pending_action!.action_id, { action_id: v20Snapshot.pending_action!.action_id, action_fingerprint: v20Snapshot.pending_action!.action_fingerprint, reviewer: "web-reviewer", decided_at: new Date().toISOString() }).then(setV20Snapshot).catch((reason) => setV20Error(reason instanceof AutonomousV20RequestError ? reason.code : "LOOP_REJECTED")); } : undefined} onReject={v20Snapshot.pending_action ? () => { void rejectAutonomousAction(v20Snapshot.pending_action!.action_id, { action_id: v20Snapshot.pending_action!.action_id, action_fingerprint: v20Snapshot.pending_action!.action_fingerprint, reviewer: "web-reviewer", decided_at: new Date().toISOString() }).then(setV20Snapshot).catch((reason) => setV20Error(reason instanceof AutonomousV20RequestError ? reason.code : "LOOP_REJECTED")); } : undefined} /><RepairProposalPanel proposal={null} />{v20Error && <p className="muted">Workflow action is unavailable.</p>}</>}</>}
    {!error && !snapshot && !loading && <section className="empty-state"><h2>Choose a project</h2><p>Load a verified, read-only loop snapshot to inspect its current state.</p></section>}
  </div>;
}
