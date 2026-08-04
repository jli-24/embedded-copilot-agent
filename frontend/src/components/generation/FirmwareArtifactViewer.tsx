import type { FirmwareArtifact } from "../../types/generation";

export function FirmwareArtifactViewer({ artifact }: { artifact: FirmwareArtifact }) {
  return <div className="artifact-viewer"><h3>Firmware proposal</h3><p>{artifact.summary}</p><dl><dt>Files</dt><dd>{artifact.files.join(" · ")}</dd><dt>Configuration</dt><dd>{artifact.configuration.join(" · ")}</dd><dt>Dependencies</dt><dd>{artifact.dependencies.join(" · ")}</dd></dl></div>;
}
