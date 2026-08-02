import { Button } from "./ui/Button";

const actions = [
  "Generate Proposal",
  "Build Firmware",
  "Flash Device",
  "Debug Session",
  "Hardware Test",
  "PID Optimization",
];

export function ActionCenter() {
  return (
    <section className="rounded-3xl bg-white p-6 shadow-panel">
      <div className="mb-5 flex items-end justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Controlled boundary</p>
          <h2 className="mt-1 text-2xl font-semibold">Engineering actions</h2>
        </div>
        <span className="rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-500">Proposal only</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {actions.map((action) => (
          <Button key={action} disabled className="text-left">
            {action}
          </Button>
        ))}
      </div>
    </section>
  );
}
