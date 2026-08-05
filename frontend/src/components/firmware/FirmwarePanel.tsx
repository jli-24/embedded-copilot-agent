import type { DebugAnalysisSnapshot } from "../../types/debug";
import type { FirmwareBuildResult, FirmwareProjectSnapshot } from "../../types/firmware";
import { BuildStatusPanel } from "./BuildStatusPanel";
import { FirmwareArtifactPanel } from "./FirmwareArtifactPanel";
import { FirmwareDebugPanel } from "./FirmwareDebugPanel";

export function FirmwarePanel({ snapshot, build, debug, error, buildError, debugError, loading }: { snapshot: FirmwareProjectSnapshot | null; build: FirmwareBuildResult | null; debug: DebugAnalysisSnapshot | null; error: string | null; buildError: string | null; debugError: string | null; loading: boolean }) {
  return <><section className="panel"><div className="panel-heading"><h2>Firmware engineering</h2><span className="status-pill status-pending">Read-only</span></div>{loading && <p className="muted">Loading firmware projection...</p>}{!loading && error && <p className="muted">Firmware projection is unavailable.</p>}{!loading && !error && snapshot && <><p>Framework: {snapshot.framework}</p><p className="muted">Build profile: {snapshot.build_configuration.profile}</p></>}</section>{snapshot && <FirmwareArtifactPanel snapshot={snapshot} />}<BuildStatusPanel result={build} error={buildError} loading={loading} /><FirmwareDebugPanel snapshot={debug} error={debugError} loading={loading} /></>;
}
