import type { ComponentRecommendation } from "../../types/components";
export function ComponentRecommendationPanel({ items, error, loading }: { items: ComponentRecommendation[] | null; error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Component Recommendations</h2><span className="status-pill status-pending">Read-only</span></div>
    {loading && <p className="muted">Loading recommendations...</p>}
    {!loading && error && <p className="muted">Component recommendations are unavailable.</p>}
    {!loading && !error && items && (items.length === 0 ? <p className="muted">No recommendations are available.</p> : <div className="recommendation-list">{items.map((item) => <div className="proposal-block" key={item.part_number}><strong>{item.part_number} · {item.manufacturer}</strong><span>{item.reason}</span><span>Datasheet: {item.datasheet_reference}</span><span>Supplier links: {item.supplier_links.join(", ") || "None"}</span><span>Alternatives: {item.alternatives.join(", ") || "None"}</span></div>)}</div>)}
  </section>;
}
