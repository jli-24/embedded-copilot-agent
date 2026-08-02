import type { ReportProjection } from "../types/contracts";

export function ReportViewer({ report }: { report?: ReportProjection }) {
  if (!report) {
    return <div className="rounded-3xl bg-white p-6 text-stone-500 shadow-panel">Report projection unavailable.</div>;
  }
  return (
    <section className="rounded-3xl bg-white p-6 shadow-panel">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Engineering release report</p>
      <h2 className="mt-2 text-2xl font-semibold">{report.project_name}</h2>
      <p className="mt-2 text-sm leading-6 text-stone-600">{report.project_summary}</p>
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {report.sections.map((section) => (
          <div key={section.stage} className="rounded-2xl border border-stone-200 p-4">
            <strong className="text-sm">{section.stage}</strong>
            <p className="mt-1 text-xs text-stone-500">{section.status}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
