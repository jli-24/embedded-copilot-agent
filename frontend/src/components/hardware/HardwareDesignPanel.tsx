import type { UnifiedHardwareModel } from "../../types/hardware";
import { ComponentTable } from "./ComponentTable";
import { NetTable } from "./NetTable";
import { InterfacePanel } from "./InterfacePanel";

export function HardwareDesignPanel({ model, error, loading }: { model: UnifiedHardwareModel | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Hardware design</h2><span className="status-pill status-pending">Read-only</span></div>{loading && <p className="muted">Loading hardware design...</p>}{!loading && error && <p className="muted">Hardware design is unavailable.</p>}{!loading && !error && model && <><p className="muted">Source: {model.design_source_type}</p><h3>Components</h3><ComponentTable items={model.components} /><h3>Nets</h3><NetTable items={model.nets} /><h3>Interfaces</h3><InterfacePanel items={model.interfaces} /><h3>Layers</h3><p className="muted">{model.layers.map((layer) => `${layer.name} (${layer.layer_type})`).join(", ") || "Unresolved"}</p><h3>Constraints</h3><p className="muted">{model.constraints.join("; ") || "Unresolved"}</p></>}</section>;
}
