import type { FirmwareProposal } from "../types/contracts";

export function ArtifactViewer({ proposal }: { proposal?: FirmwareProposal }) {
  return (
    <section className="rounded-2xl bg-white p-6 shadow-panel">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">Artifact Viewer</p>
          <h2 className="mt-1 text-xl font-semibold">Firmware proposal</h2>
        </div>
        <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
          {proposal ? "Review required" : "Not generated"}
        </span>
      </div>
      {!proposal ? (
        <p className="mt-5 text-sm text-stone-500">Generate a proposal to inspect its safe logical files.</p>
      ) : (
        <div className="mt-5 space-y-4">
          {proposal.files.map((file) => (
            <article key={file.fingerprint} className="overflow-hidden rounded-xl border border-stone-200">
              <header className="flex justify-between bg-stone-50 px-4 py-2 text-xs font-semibold">
                <span>{file.logical_path}</span><span>{file.purpose}</span>
              </header>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap p-4 text-xs text-stone-700">{file.content}</pre>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
