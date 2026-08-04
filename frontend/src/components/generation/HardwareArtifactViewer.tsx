import type { HardwareArtifact } from "../../types/generation";

export function HardwareArtifactViewer({ artifact }: { artifact: HardwareArtifact }) {
  return <div className="artifact-viewer"><h3>Hardware proposal</h3><p>{artifact.summary}</p><div className="proposal-block"><strong>{artifact.system_architecture.system}</strong><span>{artifact.system_architecture.components.join(" · ")}</span></div>
    <div className="proposal-block"><strong>Interfaces</strong>{artifact.interface_contracts.map((item) => <span key={item.name}>{item.name}: {item.protocol} · {item.status}</span>)}</div>
    <div className="proposal-block"><strong>BOM proposal</strong>{artifact.bom.map((item) => <span key={item.component}>{item.component}: {item.status} · {item.risk}</span>)}</div>
  </div>;
}
