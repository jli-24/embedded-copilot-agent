import type { DeviceSnapshot } from "../../types/device";
export function DevicePanel({ snapshot, error, loading }: { snapshot: DeviceSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Device</h2><span className="status-pill status-pending">Read-only</span></div>{loading && <p className="muted">Loading device status...</p>}{!loading && error && <p className="muted">Device status is unavailable.</p>}{!loading && !error && snapshot && <dl className="runtime-details"><dt>Device</dt><dd>{snapshot.device_id}</dd><dt>Type</dt><dd>{snapshot.device_type}</dd><dt>Connection</dt><dd>{snapshot.connection_status}</dd></dl>}</section>;
}
