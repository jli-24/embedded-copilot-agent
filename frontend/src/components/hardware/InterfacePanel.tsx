import type { InterfaceProjection } from "../../types/hardware";

export function InterfacePanel({ items }: { items: InterfaceProjection[] }) {
  return <dl className="runtime-details">{items.map((item) => <div key={item.name}><dt>{item.name}</dt><dd>{item.protocol}: {item.signals.join(", ") || "Unresolved"}</dd></div>)}</dl>;
}
