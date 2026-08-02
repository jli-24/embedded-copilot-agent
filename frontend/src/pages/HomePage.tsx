import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { Button } from "../components/ui/Button";

export function HomePage() {
  const navigate = useNavigate();
  const [requirement, setRequirement] = useState("Design a low-power WiFi camera");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject(requirement);
      navigate(`/projects/${project.project_id}`);
    } catch {
      setError("The project could not be prepared.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-paper px-6 py-16 text-ink">
      <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">
        <section>
          <p className="text-sm font-bold uppercase tracking-[0.28em] text-accent">Embedded Copilot · Web Console</p>
          <h1 className="mt-5 max-w-3xl text-5xl font-semibold leading-[1.05] sm:text-7xl">Engineering clarity, from requirement to report.</h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-stone-600">A review-first interface over deterministic engineering projections. It observes and prepares; it never bypasses approval.</p>
        </section>
        <form onSubmit={submit} className="rounded-[2rem] bg-white p-8 shadow-panel">
          <label className="text-sm font-semibold" htmlFor="requirement">Start with an engineering requirement</label>
          <textarea id="requirement" value={requirement} onChange={(event) => setRequirement(event.target.value)} className="mt-3 min-h-44 w-full rounded-2xl border border-stone-200 bg-stone-50 p-4 outline-none focus:border-accent" />
          <Button className="mt-5 w-full" disabled={busy || !requirement.trim()}>{busy ? "Preparing…" : "Create project"}</Button>
          {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
        </form>
      </div>
    </main>
  );
}
