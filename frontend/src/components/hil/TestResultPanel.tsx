import type { TestCaseProjection } from "../../types/hil";

export function TestResultPanel({ cases }: { cases: TestCaseProjection[] }) {
  return <div className="review-list">{cases.map((testCase) => <article key={testCase.name}><div className="panel-heading"><strong>{testCase.name}</strong><span>{testCase.status}</span></div><p className="muted">{testCase.summary}</p></article>)}</div>;
}
