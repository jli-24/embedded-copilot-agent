import { Fragment } from "react";
import type { DeviceObservationSnapshot } from "../../types/hil";

export function DeviceObservationPanel({ snapshot, error, loading }: { snapshot: DeviceObservationSnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Device observation</h2><span className="status-pill status-running">Projection</span></div>{loading && <p className="muted">Loading observation...</p>}{!loading && error && <p className="muted">Device observation is unavailable.</p>}{!loading && !error && snapshot && <><p>Status: {snapshot.status}</p><p className="muted">Type: {snapshot.observation_type}</p><dl className="runtime-details">{snapshot.metrics.map((metric, index) => <Fragment key={`${metric.name}-${index}`}><dt>{metric.name}</dt><dd>{metric.value}</dd></Fragment>)}</dl></>}</section>;
}
