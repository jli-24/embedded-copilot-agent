import type { FirmwareBuildResult } from "../../types/firmware";

export function BuildStatusPanel({ result, error, loading }: { result: FirmwareBuildResult | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Firmware build</h2><span className="status-pill status-pending">Projection</span></div>{loading && <p className="muted">Loading build status...</p>}{!loading && error && <p className="muted">Build status is unavailable.</p>}{!loading && !error && result && <><p>Status: {result.build_status}</p><p className="muted">Artifact: {result.artifact_reference}</p><p className="muted">{result.summary}</p></>}</section>;
}
