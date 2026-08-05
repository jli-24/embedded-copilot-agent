import type { MetricsProjection } from "../../types/digitalTwin";

export function MetricsPanel({ metrics }: { metrics: MetricsProjection }) {
  return <div className="review-list"><p>CPU: {metrics.cpu_usage}</p><p>Memory: {metrics.memory_usage}</p><p>Flash: {metrics.flash_usage}</p><p>RAM: {metrics.ram_usage}</p><p>Latency: {metrics.latency}</p><p>Power: {metrics.power_estimate}</p><p>Communication: {metrics.communication_quality}</p></div>;
}
