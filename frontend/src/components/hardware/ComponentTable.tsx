import type { ComponentProjection } from "../../types/hardware";

export function ComponentTable({ items }: { items: ComponentProjection[] }) {
  return <div className="table-wrap"><table><thead><tr><th>Reference</th><th>Value</th><th>Footprint</th><th>Manufacturer</th><th>Part</th><th>Status</th></tr></thead><tbody>{items.map((item) => <tr key={item.reference}><td>{item.reference}</td><td>{item.value ?? "Unresolved"}</td><td>{item.footprint ?? "Unresolved"}</td><td>{item.manufacturer ?? "Unresolved"}</td><td>{item.part_number ?? "Unresolved"}</td><td>{item.status}</td></tr>)}</tbody></table></div>;
}
