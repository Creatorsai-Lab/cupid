import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applyEvent,
  initialRunView,
  RUN_EVENT_TYPES,
  subscribeToRun,
  type RunEvent,
  type RunView,
} from "@/lib/runEvents";

const RUN = "run-1";

function ev(type: RunEvent["type"], step: string | null = null, data = {}): RunEvent {
  return { run_id: RUN, type, step, data };
}

function replay(events: RunEvent[]): RunView {
  return events.reduce(applyEvent, initialRunView());
}

const piece = (id: string, text: string) => ({
  id,
  deliverable: "linkedin_post",
  variant: 1,
  blocks: [{ kind: "text", role: null, text }],
  source_ids: [],
  status: "ready",
});

describe("applyEvent", () => {
  it("follows a run step by step to completion", () => {
    const view = replay([
      ev("run.started", null, { resumed: false }),
      ev("step.started", "supervisor"),
      ev("step.finished", "supervisor"),
      ev("step.started", "research"),
      ev("research.sources", "research", {
        status: "complete",
        sources: [{ id: "S1", title: "A study", url: "https://example.com/a" }],
      }),
      ev("step.finished", "research"),
      ev("step.started", "studio"),
      ev("piece.ready", "studio", piece("p1", "Draft one")),
      ev("step.finished", "studio"),
      ev("run.completed", null, { pieces: 1 }),
    ]);

    expect(view.status).toBe("completed");
    expect(view.steps).toEqual({ supervisor: "done", research: "done", studio: "done" });
    expect(view.sources.map((s) => s.id)).toEqual(["S1"]);
    expect(view.pieces.map((p) => p.blocks[0].text)).toEqual(["Draft one"]);
  });

  it("shows the running step while a run is in progress", () => {
    const view = replay([
      ev("run.started"),
      ev("step.started", "supervisor"),
      ev("step.finished", "supervisor"),
      ev("step.started", "research"),
    ]);

    expect(view.status).toBe("running");
    expect(view.steps).toEqual({ supervisor: "done", research: "running", studio: "pending" });
  });

  it("marks the interrupted step failed and keeps the user's message", () => {
    const view = replay([
      ev("run.started"),
      ev("step.started", "research"),
      ev("run.failed", null, { message: "Something went wrong.", resume_later: false }),
    ]);

    expect(view.status).toBe("failed");
    expect(view.steps.research).toBe("failed");
    expect(view.message).toBe("Something went wrong.");
  });

  it("knows when a failed run will continue by itself", () => {
    const paused = replay([
      ev("run.started"),
      ev("run.failed", null, { message: "Something went wrong.", resume_later: true }),
    ]);
    expect(paused.autoResume).toBe(true);

    expect(applyEvent(paused, ev("run.started", null, { resumed: true })).autoResume).toBe(false);
  });

  it("picks up again after a resume, as a page reload replays it", () => {
    const view = replay([
      ev("run.started"),
      ev("step.started", "supervisor"),
      ev("step.finished", "supervisor"),
      ev("step.started", "research"),
      ev("run.failed", null, { message: "Something went wrong." }),
      ev("run.started", null, { resumed: true }),
      ev("step.started", "research"),
    ]);

    expect(view.status).toBe("running");
    expect(view.message).toBeNull();
    expect(view.steps).toEqual({ supervisor: "done", research: "running", studio: "pending" });
  });

  it("never shows the same piece twice", () => {
    const view = replay([
      ev("piece.ready", "studio", piece("p1", "First take")),
      ev("piece.ready", "studio", piece("p1", "Rewritten")),
    ]);

    expect(view.pieces.map((p) => p.blocks[0].text)).toEqual(["Rewritten"]);
  });

  it("tells the user why a run was blocked", () => {
    const view = replay([
      ev("run.started"),
      ev("run.blocked", null, { reason: "Please describe what you want to create." }),
    ]);

    expect(view.status).toBe("blocked");
    expect(view.message).toBe("Please describe what you want to create.");
  });

  it("labels a degraded run with its issues", () => {
    const view = replay([
      ev("run.degraded", null, {
        issues: [{ step: "research", severity: "degraded", message: "Few sources" }],
        research: "low_coverage",
      }),
    ]);

    expect(view.status).toBe("degraded");
    expect(view.issues.map((i) => i.message)).toEqual(["Few sources"]);
  });
});

// ── subscribeToRun ─────────────────────────────────────────────

class FakeEventSource {
  static last: FakeEventSource;
  static CLOSED = 2;
  url: string;
  withCredentials: boolean;
  readyState = 0;
  onerror: (() => void) | null = null;
  listeners = new Map<string, (e: MessageEvent) => void>();

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.withCredentials = !!init?.withCredentials;
    FakeEventSource.last = this;
  }
  addEventListener(type: string, fn: (e: MessageEvent) => void) {
    this.listeners.set(type, fn);
  }
  close() {
    this.readyState = FakeEventSource.CLOSED;
  }
  emit(type: string, data: unknown) {
    this.listeners.get(type)?.(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
}

describe("subscribeToRun", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends the session cookie, delivers run events and closes on end", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const onEvent = vi.fn();
    const onEnd = vi.fn();

    subscribeToRun(RUN, { onEvent, onEnd, onError: vi.fn() });
    const source = FakeEventSource.last;
    source.emit("run.started", ev("run.started"));
    source.emit("end", {});

    expect(source.url).toMatch(/\/api\/v1\/agents\/runs\/run-1\/events$/);
    expect(source.withCredentials).toBe(true);
    expect(onEvent).toHaveBeenCalledWith(ev("run.started"));
    expect(onEnd).toHaveBeenCalledOnce();
    expect(source.readyState).toBe(FakeEventSource.CLOSED); // no automatic reconnect
  });

  it("listens to every run event type", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    subscribeToRun(RUN, { onEvent: vi.fn(), onEnd: vi.fn(), onError: vi.fn() });

    for (const type of RUN_EVENT_TYPES) {
      expect(FakeEventSource.last.listeners.has(type)).toBe(true);
    }
  });

  it("reports an error only when the browser gives up reconnecting", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const onError = vi.fn();
    subscribeToRun(RUN, { onEvent: vi.fn(), onEnd: vi.fn(), onError });
    const source = FakeEventSource.last;

    source.onerror?.(); // a dropped connection: the browser reconnects by itself
    expect(onError).not.toHaveBeenCalled();

    source.readyState = FakeEventSource.CLOSED; // e.g. 401 or 404: no reconnect
    source.onerror?.();
    expect(onError).toHaveBeenCalledOnce();
  });

  it("stops listening when unsubscribed", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const stop = subscribeToRun(RUN, { onEvent: vi.fn(), onEnd: vi.fn(), onError: vi.fn() });

    stop();

    expect(FakeEventSource.last.readyState).toBe(FakeEventSource.CLOSED);
  });
});
