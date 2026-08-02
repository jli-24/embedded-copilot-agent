import { useState, type ChangeEvent } from "react";

import { api } from "../api/client";
import type { AttachmentProjection } from "../types/contracts";
import { Button } from "./ui/Button";

export function AttachmentPanel({ projectId }: { projectId: string }) {
  const [file, setFile] = useState<File>();
  const [projection, setProjection] = useState<AttachmentProjection>();
  const [error, setError] = useState("");

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0]);
    setProjection(undefined);
    setError("");
  }

  async function submitMetadata() {
    if (!file) return;
    try {
      const result = await api.attachment(projectId, {
        reference_id: `attachment-${Date.now()}`,
        attachment_type: attachmentType(file.name),
        basename: file.name,
        summary: "Caller-selected attachment metadata",
        size_bytes: file.size,
        observed_at: new Date().toISOString(),
      });
      setProjection(result);
    } catch {
      setError("Attachment metadata could not be projected.");
    }
  }

  return (
    <section className="rounded-3xl border border-stone-200 bg-paper p-6">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-moss">Safe references</p>
      <h2 className="mt-1 text-2xl font-semibold">Attachment metadata</h2>
      <p className="mt-2 text-sm text-stone-600">
        Only filename, size, type and a safe summary cross the interface boundary.
      </p>
      <input className="my-5 block w-full text-sm" type="file" onChange={selectFile} />
      <Button onClick={submitMetadata} disabled={!file}>Project metadata</Button>
      {projection && <p className="mt-4 text-sm text-moss">Projected: {projection.basename}</p>}
      {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
    </section>
  );
}

function attachmentType(name: string) {
  const suffix = name.toLowerCase();
  if (suffix.endsWith(".pdf")) return "DATASHEET_PDF";
  if (suffix.endsWith(".log")) return "LOG";
  if (suffix.endsWith(".png") || suffix.endsWith(".jpg")) return "PCB_IMAGE";
  return "CODE";
}
