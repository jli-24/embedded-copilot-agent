import type { DigitalTwinSnapshot } from "../../types/digitalTwin";
import { MetricsPanel } from "./MetricsPanel";
import { ConstraintPanel } from "./ConstraintPanel";

export function DigitalTwinPanel({ snapshot, error, loading }: { snapshot: DigitalTwinSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Digital twin</h2><span className="status-pill status-pending">Read-only</span></div>{loading && <p className="muted">Loading digital twin...</p>}{!loading && error && <p className="muted">Digital twin is unavailable.</p>}{!loading && !error && snapshot && <><p className="muted">Project: {snapshot.project_id}</p><p className="muted">Hardware: {snapshot.hardware_reference} / Firmware: {snapshot.firmware_reference}</p><h3>Metrics</h3><MetricsPanel metrics={snapshot.metrics} /><h3>Constraints</h3><ConstraintPanel constraints={snapshot.constraints} /></>}</section>;
}
