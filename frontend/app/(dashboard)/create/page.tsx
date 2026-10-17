"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/lib/store";
import {
  agentsApi,
  profileApi,
  CONTENT_TYPES,
  PLATFORMS,
  LENGTHS,
  TONES,
  type ContentType,
  type Platform,
  type ContentLength,
  type Tone,
} from "@/lib/api";
import {
  applyEvent,
  initialRunView,
  subscribeToRun,
  STEPS,
  type ContentPiece,
  type RunView,
  type Source,
  type StepName,
  type StepState,
} from "@/lib/runEvents";
import {
  Send,
  Loader2,
  Compass,
  Mic,
  Upload,
  Link,
  ChevronDown,
  Check,
  X,
  Circle,
  RotateCcw,
} from "lucide-react";

// Welcome lines — one is picked at random and locked for 24h (see effect below).
const GREETINGS = [
  "What should we focus on, {name}?",
  "What's today's agenda, {name}?",
  "Let's jump in, {name}.",
  "What are we creating today, {name}?",
  "How can I help you {name}?",
];

// ── Run progress ──────────────────────────────────────────────

const STEP_LABELS: Record<StepName, string> = {
  supervisor: "Checking your request",
  research: "Researching",
  studio: "Writing drafts",
};

// MAIN PAGE

export default function CreatePage() {
  const { user } = useAuthStore();
  const [prompt, setPrompt] = useState("");
  const [contentType, setContentType] = useState<ContentType>("Text");
  const [platform, setPlatform] = useState<Platform>("Twitter");
  const [length, setLength] = useState<ContentLength>("Medium");
  const [tone, setTone] = useState<Tone>("Formal");
  const [nickname, setNickname] = useState<string | null>(null);
  const [greetIdx, setGreetIdx] = useState(0);
  const [runId, setRunId] = useState<string | null>(null);
  const [view, setView] = useState<RunView>(initialRunView);
  // Bumped to follow the same run again (after a resume).
  const [subscription, setSubscription] = useState(0);
  // The server ended the stream: the run is finished, nothing more will happen.
  const [ended, setEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const firstName = user?.full_name?.split(" ")[0] || "Creator";
  const displayName = nickname || firstName;

  const isGenerating = runId !== null && (view.status === "queued" || view.status === "running");
  // Moves the workspace up once there is something to show below it.
  const hasActiveResults = runId !== null || error !== null;

  // Fetch nickname once on mount
  useEffect(() => {
    profileApi
      .get()
      .then((res) => {
        if (res.data?.nickname) setNickname(res.data.nickname);
      })
      .catch(() => {});
  }, []);

  // Restore an unsent prompt draft so a refresh or accidentally-closed tab
  // doesn't lose the user's thinking. The draft is saved on every keystroke
  // (effect below) and cleared once the prompt is successfully sent.
  useEffect(() => {
    try {
      const draft = localStorage.getItem("cupid-prompt-draft");
      // localStorage exists only in the browser; reading it after mount avoids
      // a hydration mismatch.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (draft) setPrompt(draft);
    } catch {}
  }, []);

  // Keep the draft in sync with the textarea.
  useEffect(() => {
    try {
      if (prompt.trim()) localStorage.setItem("cupid-prompt-draft", prompt);
      else localStorage.removeItem("cupid-prompt-draft");
    } catch {}
  }, [prompt]);

  // Pick a welcome line, then keep it for 24h. Reuses the stored choice until
  // a day has passed, then rolls a fresh one — so it changes once per day, not
  // on every visit. (localStorage runs client-side → no hydration mismatch.)
  useEffect(() => {
    const KEY = "cupid-greeting";
    const DAY = 24 * 60 * 60 * 1000;
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const { i, ts } = JSON.parse(raw);
        if (typeof i === "number" && Date.now() - ts < DAY) {
          // Same reason as the draft restore above: browser-only storage, read after mount.
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setGreetIdx(i % GREETINGS.length);
          return;
        }
      }
    } catch {}
    const i = Math.floor(Math.random() * GREETINGS.length);
    setGreetIdx(i);
    try {
      localStorage.setItem(KEY, JSON.stringify({ i, ts: Date.now() }));
    } catch {}
  }, []);

  // Follow the run live. Events replay from the start, so a re-subscribe
  // (after a resume) rebuilds the same view and then continues.
  useEffect(() => {
    if (!runId) return;
    return subscribeToRun(runId, {
      onEvent: (event) => setView((v) => applyEvent(v, event)),
      onEnd: () => setEnded(true),
      onError: () => setError("Lost the connection to this run. Refresh the page to try again."),
    });
  }, [runId, subscription]);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setError(null);
    setView(initialRunView());
    setEnded(false);
    setRunId(null);

    try {
      const res = await agentsApi.generate({
        prompt,
        content_type: contentType,
        platform,
        length,
        tone,
      });
      setRunId(res.run_id);
      // Sent successfully → the draft is no longer needed.
      try {
        localStorage.removeItem("cupid-prompt-draft");
      } catch {}
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleResume = async () => {
    if (!runId) return;
    setError(null);
    try {
      await agentsApi.resume(runId);
      setView(initialRunView());
      setEnded(false);
      setSubscription((n) => n + 1);
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <main
      className={`mx-auto flex min-h-[calc(100vh-60px)] max-w-5xl flex-col transition-all duration-500 ease-in-out ${hasActiveResults ? "justify-start" : "justify-center"}`}
    >
      {/* Welcome Title */}
      <div className="mb-6 text-center">
        <h1 className="mb-2 font-[family-name:var(--font-display)] text-[clamp(1.6rem,3.5vw,2.2rem)] font-normal tracking-tight">
          {GREETINGS[greetIdx].replace("{name}", displayName)}
        </h1>
      </div>

      {/* Input Box Workplace */}
      <div className="animated-gradient-border m-3">
        <div className="animated-gradient-border-inner relative flex flex-col p-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleGenerate();
            }}
            placeholder="Describe here your idea and intent in detail what you want to create..."
            className="mb-4 w-full resize-none bg-transparent font-[family-name:var(--font-body)] text-base leading-relaxed text-[var(--color-text)] outline-none"
            rows={3}
          />

          <div className="mt-auto flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            {/* ROW 1 (Mobile): */}
            <div className="grid w-full grid-cols-4 gap-1.5 md:flex md:w-auto md:items-center md:gap-2.5">
              <SelectDropdown
                label="Type"
                options={CONTENT_TYPES}
                value={contentType}
                onChange={setContentType}
              />
              <SelectDropdown
                label="Platform"
                options={PLATFORMS}
                value={platform}
                onChange={setPlatform}
              />
              <SelectDropdown
                label="Length"
                options={LENGTHS}
                value={length}
                onChange={setLength}
              />
              <SelectDropdown label="Tone" options={TONES} value={tone} onChange={setTone} />
            </div>

            {/* ROW 2 (Mobile): Action Buttons & Icons perfectly aligned */}
            <div className="flex w-full items-center justify-between gap-4 border-t border-gray-100 pt-0 md:w-auto md:justify-end md:border-none md:pt-0">
              <div className="flex items-center gap-4 text-(--color-text)">
                <Upload
                  size={17}
                  className="shrink-0 cursor-pointer transition-all duration-200 hover:scale-93 hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]"
                />
                <Link
                  size={17}
                  className="shrink-0 cursor-pointer transition-all duration-200 hover:scale-93 hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]"
                />
                <Mic
                  size={17}
                  className="shrink-0 cursor-pointer transition-all duration-200 hover:scale-93 hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]"
                />
              </div>
              {/* Primary Generation Call Button */}
              <button
                onClick={handleGenerate}
                disabled={!prompt.trim() || isGenerating}
                className="btn-primary flex shrink-0 items-center justify-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-40"
                style={{ padding: "0.5rem 1.25rem" }}
              >
                {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Error Diagnostics Panel */}
      {error && (
        <div className="mb-5 rounded-lg border-1 border-[var(--color-destructive)] bg-[color-mix(in_srgb,var(--color-destructive)_20%,transparent)] p-4">
          <div className="flex-1">
            <p className="text-sm text-(--color-destructive)">{error}</p>
          </div>
        </div>
      )}

      {/* Live progress */}
      {runId &&
        (view.status === "queued" || view.status === "running" || view.status === "failed") && (
          <RunProgress steps={view.steps} queued={view.status === "queued"} />
        )}

      {/* Paused on the AI provider's limit: the worker continues it by itself */}
      {view.status === "failed" && view.autoResume && !ended && (
        <div className="mb-5 rounded-lg bg-(--color-inline-bg) p-4">
          <p className="text-sm text-(--color-input)">
            Paused: the AI provider&apos;s limit was reached. Cupid continues automatically in a
            minute or two.
          </p>
        </div>
      )}

      {/* Failed for good: the user can continue it from where it stopped */}
      {view.status === "failed" && ended && (
        <div className="mb-5 flex items-center justify-between gap-4 rounded-lg border-1 border-[var(--color-destructive)] bg-[color-mix(in_srgb,var(--color-destructive)_20%,transparent)] p-4">
          <p className="text-sm text-(--color-destructive)">
            {view.message || "Something went wrong while creating your content."}
          </p>
          <button
            onClick={handleResume}
            className="btn-primary flex shrink-0 items-center gap-1.5"
            style={{ padding: "0.4rem 1rem" }}
          >
            <RotateCcw size={14} /> Retry
          </button>
        </div>
      )}

      {/* Blocked: tell the user why */}
      {view.status === "blocked" && view.message && (
        <div className="mb-5 rounded-lg bg-(--color-inline-bg) p-4">
          <p className="text-sm text-(--color-input)">{view.message}</p>
        </div>
      )}

      {view.sources.length > 0 && <SourcesPanel sources={view.sources} />}

      {view.status === "degraded" && (
        <p className="mb-3 px-1 text-sm text-(--color-grayish-red)">
          Some parts were limited
          {view.issues.length > 0 ? `: ${view.issues.map((i) => i.message).join("; ")}` : "."}
        </p>
      )}

      {view.pieces.map((piece) => (
        <PieceCard key={piece.id} piece={piece} />
      ))}

      <footer className="bg-red fixed right-0 bottom-0 left-0 py-3 text-center text-sm not-italic">
        Cupid can make mistakes, please review post before publishing
      </footer>
    </main>
  );
}

// SELECT DROPDOWN
function SelectDropdown<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <select
      value={value}
      // Safe cast: the browser only reports values from the <option>s rendered from `options`.
      onChange={(e) => onChange(e.target.value as T)}
      title={label}
      className="w-full cursor-pointer truncate rounded-full border-none bg-(--color-inline-bg) px-1 py-1 text-center font-[family-name:var(--font-body)] text-[0.75rem] text-(--color-text) outline-none md:px-3 md:text-left md:text-[0.8rem]"
    >
      {options.map((opt) => (
        <option
          key={opt}
          value={opt}
          className="bg-(--color-inline-bg) font-sans text-(--color-text)"
        >
          {opt}
        </option>
      ))}
    </select>
  );
}

// RUN PROGRESS
function RunProgress({ steps, queued }: { steps: Record<StepName, StepState>; queued: boolean }) {
  return (
    <div className="mb-5 rounded-lg bg-(--inline-bg) px-5 py-3">
      {queued && <p className="mb-2 text-sm text-(--color-input)">Waiting for a free worker…</p>}
      <ol className="flex flex-col gap-1.5 md:flex-row md:gap-6">
        {STEPS.map((step) => (
          <li key={step} className="flex items-center gap-2 text-sm text-(--color-input)">
            <StepIcon state={steps[step]} />
            <span className={steps[step] === "pending" ? "opacity-50" : "font-medium"}>
              {STEP_LABELS[step]}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function StepIcon({ state }: { state: StepState }) {
  const className = "flex-shrink-0 text-[var(--color-primary)]";
  if (state === "running") return <Loader2 size={14} className={`animate-spin ${className}`} />;
  if (state === "done") return <Check size={14} className={className} />;
  if (state === "failed")
    return <X size={14} className="flex-shrink-0 text-(--color-destructive)" />;
  return <Circle size={14} className={`opacity-40 ${className}`} />;
}

// RESEARCH SOURCES
function SourcesPanel({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-2 overflow-hidden">
      <button
        onClick={() => setOpen((p) => !p)}
        className="mb-1.5 flex w-full items-center gap-3 rounded-2xl bg-(--color-inline-bg) px-4 py-1.5"
      >
        <Compass size={14} className="flex-shrink-0 text-[var(--color-primary)]" />
        <span className="flex-1 text-left text-sm font-medium tracking-wide text-(--color-input)">
          Research: {sources.length} {sources.length === 1 ? "source" : "sources"}
        </span>
        <ChevronDown size={14} className="flex-shrink-0 text-[var(--color-primary)]" />
      </button>
      {open && (
        <ul className="mx-5 divide-y divide-[var(--color-border)] rounded-2xl border border-[var(--color-border)]">
          {sources.map((s) => (
            <li key={s.id} className="px-4 py-2 text-sm">
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="flex gap-3">
                <span className="font-medium text-[var(--color-text)]">{s.title}</span>
                <span className="truncate text-[var(--color-muted)]">{hostname(s.url)}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// DRAFTED PIECE
function PieceCard({ piece }: { piece: ContentPiece }) {
  return (
    <article className="mb-4 rounded-2xl border border-[var(--color-border)] p-5">
      <p className="mb-2 text-xs tracking-wide text-[var(--color-muted)] uppercase">
        {piece.deliverable.replace(/_/g, " ")} · variant {piece.variant}
      </p>
      {piece.blocks.map((block, i) => (
        <p
          key={i}
          className="mb-2 text-base leading-relaxed whitespace-pre-wrap text-[var(--color-text)]"
        >
          {block.text}
        </p>
      ))}
    </article>
  );
}
