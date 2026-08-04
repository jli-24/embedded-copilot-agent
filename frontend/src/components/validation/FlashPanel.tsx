export function FlashPanel({ error, loading }: { error: string | null; loading: boolean }) {
  return <section className="panel"><div className="panel-heading"><h2>Flash</h2><span className="status-pill status-pending">Controlled</span></div>{loading && <p className="muted">Loading flash status...</p>}{!loading && error && <p className="muted">Flash is unavailable for this read-only console.</p>}{!loading && !error && <p className="muted">Flash remains behind an explicit capability and approval boundary.</p>}</section>;
}
