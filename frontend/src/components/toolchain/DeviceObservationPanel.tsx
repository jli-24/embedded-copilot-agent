import type { ObservationSnapshot } from "../../types/toolAdapter";

export function DeviceObservationPanel({ snapshot, error, loading }: { snapshot: ObservationSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Adapter observation</h2><span className="status-pill status-pending">Read-only</span></div>
    {loading && <p className="muted">Loading device observation...</p>}
    {!loading && error && <p className="muted">Device observation is unavailable.</p>}
    {!loading && !error && snapshot && <dl className="runtime-details"><dt>Device</dt><dd>{snapshot.device_id}</dd><dt>Boot</dt><dd>{snapshot.boot_status}</dd><dt>Firmware</dt><dd>{snapshot.firmware_version}</dd><dt>Health</dt><dd>{snapshot.health_status}</dd><dt>Summary</dt><dd>{snapshot.error_summary || "No reported errors"}</dd></dl>}
  </section>;
}
