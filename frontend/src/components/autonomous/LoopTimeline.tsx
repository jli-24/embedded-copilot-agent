import type { LoopTimelineItem } from "../../types/autonomous";

export function LoopTimeline({ items }: { items: LoopTimelineItem[] }) {
  return <ol className="timeline" aria-label="Engineering loop timeline">
    {items.map((item) => <li key={item.stage} className={`timeline-item status-${item.status.toLowerCase()}`}>
      <span className="timeline-marker" aria-hidden="true" />
      <div><strong>{item.label}</strong><span className="status-label">{item.status}</span>
        {item.summary && <p>{item.summary}</p>}</div>
    </li>)}
  </ol>;
}
