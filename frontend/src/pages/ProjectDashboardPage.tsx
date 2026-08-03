import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { ActionCenter } from "../components/ActionCenter";
import { ArtifactViewer } from "../components/ArtifactViewer";
import { AttachmentPanel } from "../components/AttachmentPanel";
import { EngineeringPipeline } from "../components/EngineeringPipeline";
import { BuildPanel } from "../components/BuildPanel";
import { EngineeringChatPanel } from "../components/EngineeringChatPanel";
import { ReportViewer } from "../components/ReportViewer";
import { Timeline } from "../components/Timeline";
import { ObservationTimeline } from "../components/ObservationTimeline";
import { Progress } from "../components/ui/Progress";
import type { DashboardProjection, FirmwareProposal, ReportProjection, TimelineProjection, WebBuildResultProjection } from "../types/contracts";

export function ProjectDashboardPage() {
  const { projectId = "" } = useParams();
  const [dashboard, setDashboard] = useState<DashboardProjection>();
  const [timeline, setTimeline] = useState<TimelineProjection>();
  const [report, setReport] = useState<ReportProjection>();
  const [firmware, setFirmware] = useState<FirmwareProposal>();
  const [build, setBuild] = useState<WebBuildResultProjection>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([api.dashboard(projectId), api.timeline(projectId), api.report(projectId)])
      .then(([nextDashboard, nextTimeline, nextReport]) => {
        if (!active) return;
        setDashboard(nextDashboard);
        setTimeline(nextTimeline);
        setReport(nextReport);
      })
      .catch(() => active && setError("The safe project projections are unavailable."));
    return () => { active = false; };
  }, [projectId]);

  async function generateFirmware() {
    setBusy(true);
    setError("");
    try { setFirmware(await api.generateFirmware(projectId)); }
    catch { setError("Firmware proposal generation is unavailable."); }
    finally { setBusy(false); }
  }

  async function startBuild() {
    if (!firmware) return;
    setBusy(true);
    setError("");
    try { setBuild(await api.startBuild(firmware)); }
    catch { setError("Controlled build execution is unavailable."); }
    finally { setBusy(false); }
  }

  if (error) return <main className="p-10 text-red-700">{error}</main>;
  if (!dashboard) return <main className="p-10 text-stone-500">Loading engineering projections…</main>;

  return (
    <main className="min-h-screen bg-paper px-5 py-8 text-ink sm:px-8">
      <div className="mx-auto max-w-[1500px]">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-5">
          <div>
            <Link to="/" className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Embedded Copilot</Link>
            <h1 className="mt-2 text-4xl font-semibold">{dashboard.project_name}</h1>
            <p className="mt-2 text-stone-600">Current stage · {dashboard.current_stage}</p>
          </div>
          <div className="min-w-64 rounded-2xl bg-white p-4 shadow-panel">
            <div className="mb-2 flex justify-between text-sm"><span>Overall progress</span><strong>{Math.round(dashboard.overall_progress)}%</strong></div>
            <Progress value={dashboard.overall_progress} />
          </div>
        </header>
        <EngineeringPipeline stages={dashboard.stages} />
        <div className="mt-8 grid gap-8 xl:grid-cols-[1fr_360px]">
          <div className="space-y-8"><EngineeringChatPanel projectId={projectId} /><BuildPanel proposal={firmware} build={build} busy={busy} onGenerate={generateFirmware} onBuild={startBuild} /><ArtifactViewer proposal={firmware} /><ReportViewer report={report} /><ActionCenter /></div>
          <div className="space-y-8"><ObservationTimeline build={build} /><Timeline timeline={timeline} /><AttachmentPanel projectId={projectId} /></div>
        </div>
      </div>
    </main>
  );
}
