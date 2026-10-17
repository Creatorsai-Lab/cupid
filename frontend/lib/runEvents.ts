/**
 * A run's live progress: the backend streams events (Server-Sent Events) and
 * `applyEvent` folds them into what the create page shows.
 *
 * Replaying a run's events from the start always gives its current state, so a
 * page reload or a resume just re-subscribes. The server ends the stream with
 * an `end` event once the run is finished; we close then, because EventSource
 * would otherwise reconnect forever.
 */

import { API_BASE } from "@/lib/api";

export const RUN_EVENT_TYPES = [
  "run.started",
  "step.started",
  "step.finished",
  "research.sources",
  "piece.ready",
  "run.degraded",
  "run.failed",
  "run.blocked",
  "run.completed",
] as const;

export type RunEventType = (typeof RUN_EVENT_TYPES)[number];
export type RunStatus = "queued" | "running" | "completed" | "degraded" | "failed" | "blocked";

export interface RunEvent {
  run_id: string;
  type: RunEventType;
  step: string | null;
  data: Record<string, unknown>;
}

export interface Source {
  id: string;
  title: string;
  url: string;
  published_at?: string | null;
}

export interface TextBlock {
  kind: "text";
  role: string | null;
  text: string;
}

export interface ContentPiece {
  id: string;
  deliverable: string;
  variant: number;
  blocks: TextBlock[];
  source_ids: string[];
  status: "ready" | "degraded" | "failed";
}

export interface Issue {
  step: string;
  severity: "warning" | "degraded" | "error";
  message: string;
}

export const STEPS = ["supervisor", "research", "studio"] as const;
export type StepName = (typeof STEPS)[number];
export type StepState = "pending" | "running" | "done" | "failed";

export interface RunView {
  status: RunStatus;
  steps: Record<StepName, StepState>;
  sources: Source[];
  researchStatus: string | null;
  pieces: ContentPiece[];
  issues: Issue[];
  message: string | null; // why it failed or was blocked
  autoResume: boolean; // failed on provider quota: the worker continues it by itself
}

export function initialRunView(): RunView {
  return {
    status: "queued",
    steps: { supervisor: "pending", research: "pending", studio: "pending" },
    sources: [],
    researchStatus: null,
    pieces: [],
    issues: [],
    message: null,
    autoResume: false,
  };
}

function isStep(step: string | null): step is StepName {
  return (STEPS as readonly string[]).includes(step ?? "");
}

function setStep(view: RunView, step: string | null, state: StepState): RunView {
  return isStep(step) ? { ...view, steps: { ...view.steps, [step]: state } } : view;
}

export function applyEvent(view: RunView, event: RunEvent): RunView {
  const data = event.data;
  switch (event.type) {
    case "run.started":
      return { ...view, status: "running", message: null, autoResume: false };
    case "step.started":
      return setStep(view, event.step, "running");
    case "step.finished":
      return setStep(view, event.step, "done");
    case "research.sources":
      return {
        ...view,
        sources: (data.sources as Source[]) ?? [],
        researchStatus: (data.status as string) ?? null,
      };
    case "piece.ready": {
      const piece = data as unknown as ContentPiece;
      const known = view.pieces.some((p) => p.id === piece.id);
      const pieces = known
        ? view.pieces.map((p) => (p.id === piece.id ? piece : p)) // a replay or a rewrite
        : [...view.pieces, piece];
      return { ...view, pieces };
    }
    case "run.completed":
      return { ...view, status: "completed" };
    case "run.degraded":
      return { ...view, status: "degraded", issues: (data.issues as Issue[]) ?? [] };
    case "run.blocked":
      return { ...view, status: "blocked", message: (data.reason as string) ?? null };
    case "run.failed": {
      const steps = { ...view.steps };
      for (const step of STEPS) if (steps[step] === "running") steps[step] = "failed";
      return {
        ...view,
        status: "failed",
        steps,
        message: (data.message as string) ?? null,
        autoResume: data.resume_later === true,
      };
    }
  }
}

interface Handlers {
  onEvent: (event: RunEvent) => void;
  onEnd: () => void;
  onError: () => void; // the connection is gone for good (e.g. signed out)
}

/** Follow a run's events; returns a function that stops listening. */
export function subscribeToRun(runId: string, { onEvent, onEnd, onError }: Handlers): () => void {
  const source = new EventSource(`${API_BASE}/api/v1/agents/runs/${runId}/events`, {
    withCredentials: true, // the session cookie (API on another origin in dev)
  });
  for (const type of RUN_EVENT_TYPES) {
    source.addEventListener(type, (e) => onEvent(JSON.parse((e as MessageEvent).data)));
  }
  source.addEventListener("end", () => {
    source.close();
    onEnd();
  });
  source.onerror = () => {
    // A dropped connection is retried by the browser (with Last-Event-ID);
    // CLOSED means it gave up, e.g. on 401 or 404.
    if (source.readyState === EventSource.CLOSED) onError();
  };
  return () => source.close();
}
