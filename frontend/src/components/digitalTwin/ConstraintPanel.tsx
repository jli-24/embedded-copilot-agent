import type { ConstraintProjection } from "../../types/digitalTwin";

export function ConstraintPanel({ constraints }: { constraints: ConstraintProjection[] }) {
  return <div className="review-list">{constraints.map((constraint) => <article key={constraint.reference}><strong>{constraint.constraint_type}</strong><p className="muted">{constraint.status}</p></article>)}</div>;
}
