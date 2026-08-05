import type { NetProjection } from "../../types/hardware";

export function NetTable({ items }: { items: NetProjection[] }) {
  return <div className="table-wrap"><table><thead><tr><th>Net</th><th>Connections</th><th>Signal</th></tr></thead><tbody>{items.map((item) => <tr key={item.name}><td>{item.name}</td><td>{item.connections.join(", ")}</td><td>{item.signal_type}</td></tr>)}</tbody></table></div>;
}
