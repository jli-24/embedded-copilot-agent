import type { TimelineProjection } from "../types/contracts";

export function Timeline({ timeline }: { timeline?: TimelineProjection }) {
  return (
    <section className="rounded-3xl bg-ink p-6 text-white shadow-panel">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-300">Traceable history</p>
      <h2 className="mt-1 text-2xl font-semibold">Project timeline</h2>
      <ol className="mt-5 space-y-4 border-l border-white/20 pl-5">
        {timeline?.events.map((item) => (
          <li key={item.fingerprint}>
            <p className="font-medium">{item.event}</p>
            <p className="text-xs text-white/55">{item.reference_type} · {item.reference_id}</p>
          </li>
        )) ?? <li className="text-sm text-white/60">No projected events.</li>}
      </ol>
    </section>
  );
}
