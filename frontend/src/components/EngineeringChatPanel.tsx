import { FormEvent, useState } from "react";

import { api } from "../api/client";
import type {
  EngineeringChatResponse,
  FeedbackType,
} from "../types/contracts";
import { Button } from "./ui/Button";

const feedbackActions: { label: string; type: FeedbackType }[] = [
  { label: "Accept", type: "ACCEPT" },
  { label: "Reject", type: "REJECT" },
  { label: "Modify", type: "MODIFY" },
  { label: "Question", type: "QUESTION" },
  { label: "Correct", type: "CORRECT" },
  { label: "Approve", type: "APPROVE" },
];

export function EngineeringChatPanel({ projectId }: { projectId: string }) {
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState<EngineeringChatResponse>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim() || busy) return;
    setBusy(true);
    setNotice("");
    try {
      setResponse(await api.chat(projectId, message.trim()));
    } catch {
      setNotice("Engineering AI is currently unavailable.");
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(type: FeedbackType) {
    if (!response) return;
    try {
      const projection = await api.feedback(
        projectId,
        type,
        `${type} the current engineering response.`,
      );
      setNotice(`Feedback recorded: ${projection.feedback_type}`);
    } catch {
      setNotice("Feedback projection is unavailable.");
    }
  }

  return (
    <section className="rounded-3xl bg-white p-6 shadow-panel">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">
            Verified context · proposal only
          </p>
          <h2 className="mt-1 text-2xl font-semibold">Engineering AI</h2>
        </div>
        <span className="rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-500">
          Human review required
        </span>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask for a requirement, architecture, hardware, or risk review…"
          maxLength={1024}
          className="min-h-24 flex-1 rounded-2xl border border-stone-200 bg-paper p-4 outline-none focus:border-accent"
        />
        <Button type="submit" disabled={busy || !message.trim()}>
          {busy ? "Reviewing…" : "Ask AI"}
        </Button>
      </form>

      {response && (
        <div className="mt-6 space-y-5">
          <ResponseSection title="Requirement analysis" value={response.requirement_analysis} />
          <ResponseSection title="Architecture recommendation" value={response.architecture_recommendation} />
          <ResponseSection title="Hardware suggestion" value={response.hardware_suggestion} />
          <ResponseSection title="Risk analysis" value={response.risk_analysis} />
          <ResponseSection title="Next action" value={response.next_action} />

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
              Progress events
            </h3>
            <ol className="mt-2 grid gap-2 text-sm">
              {response.events.map((event) => (
                <li key={event.fingerprint} className="rounded-xl bg-paper px-3 py-2">
                  {event.sequence}. {event.stage} · {event.status}
                </li>
              ))}
            </ol>
          </div>

          <div className="flex flex-wrap gap-2">
            {feedbackActions.map((action) => (
              <Button
                key={action.type}
                type="button"
                className="px-4 py-2"
                onClick={() => sendFeedback(action.type)}
              >
                {action.label}
              </Button>
            ))}
          </div>
        </div>
      )}

      {notice && <p className="mt-4 text-sm text-stone-600">{notice}</p>}
    </section>
  );
}

function ResponseSection({ title, value }: { title: string; value: string }) {
  return (
    <section>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
        {title}
      </h3>
      <p className="mt-1 leading-7 text-stone-800">{value}</p>
    </section>
  );
}
