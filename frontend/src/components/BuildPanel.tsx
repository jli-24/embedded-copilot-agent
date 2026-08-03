import type { FirmwareProposal, WebBuildResultProjection } from "../types/contracts";
import { Button } from "./ui/Button";

interface BuildPanelProps {
  proposal?: FirmwareProposal;
  build?: WebBuildResultProjection;
  busy: boolean;
  onGenerate: () => void;
  onBuild: () => void;
}

export function BuildPanel({ proposal, build, busy, onGenerate, onBuild }: BuildPanelProps) {
  return (
    <section className="rounded-2xl bg-white p-6 shadow-panel">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">Controlled execution</p>
      <h2 className="mt-1 text-xl font-semibold">Build Panel</h2>
      <div className="mt-5 flex flex-wrap gap-3">
        <Button onClick={onGenerate} disabled={busy}>Generate firmware</Button>
        <Button onClick={onBuild} disabled={busy || !proposal}>Start approved build</Button>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
        <dt className="text-stone-500">Build status</dt><dd className="font-semibold">{build?.result.status ?? "NOT_STARTED"}</dd>
        <dt className="text-stone-500">Error category</dt><dd className="font-semibold">{build?.observation.repair.category ?? "NONE"}</dd>
      </dl>
    </section>
  );
}
