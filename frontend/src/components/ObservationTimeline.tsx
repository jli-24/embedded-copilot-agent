import type { WebBuildResultProjection } from "../types/contracts";

export function ObservationTimeline({ build }: { build?: WebBuildResultProjection }) {
  const observation = build?.observation;
  return (
    <section className="rounded-2xl bg-white p-6 shadow-panel">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">Observation Timeline</p>
      <h2 className="mt-1 text-xl font-semibold">Safe engineering observations</h2>
      {!observation ? (
        <p className="mt-4 text-sm text-stone-500">No controlled build observation yet.</p>
      ) : (
        <div className="mt-4 border-l-2 border-accent pl-4 text-sm">
          <strong>{observation.observation.observation_type}</strong>
          <p className="mt-1 text-stone-600">
            {observation.observation.diagnostic_codes.join(", ") || "No diagnostic finding"}
          </p>
          {observation.repair.suggestion_codes.map((code) => <p key={code} className="mt-2 text-amber-800">{code}</p>)}
        </div>
      )}
    </section>
  );
}
