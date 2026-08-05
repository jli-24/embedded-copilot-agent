import type { FirmwareProjectSnapshot } from "../../types/firmware";

export function FirmwareArtifactPanel({ snapshot }: { snapshot: FirmwareProjectSnapshot }) {
  return <section className="panel"><div className="panel-heading"><h2>Firmware artifact</h2><span className="status-pill status-pending">Read-only</span></div><p className="muted">Reference: {snapshot.firmware_reference}</p><p className="muted">Targets: {snapshot.targets.join(", ") || "Unresolved"}</p><p className="muted">Sources: {snapshot.source_projection.source_count} ({snapshot.source_projection.header_count} headers)</p></section>;
}
