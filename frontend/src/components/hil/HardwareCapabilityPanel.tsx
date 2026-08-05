import type { HardwareCapabilitySnapshot } from "../../types/hil";

export function HardwareCapabilityPanel({ snapshot, error, loading }: { snapshot: HardwareCapabilitySnapshot | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Hardware capability</h2><span className="status-pill status-pending">Read-only</span></div>{loading && <p className="muted">Loading capability...</p>}{!loading && error && <p className="muted">Hardware capability is unavailable.</p>}{!loading && !error && snapshot && <><p>Board: {snapshot.board_type}</p><p>Chip: {snapshot.chip_family}</p><p className="muted">Interfaces: {snapshot.interfaces.join(", ") || "Unresolved"}</p><p className="muted">Capabilities: {snapshot.capabilities.join(", ") || "Unresolved"}</p></>}</section>;
}
