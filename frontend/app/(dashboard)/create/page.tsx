"use client";

import { useState, useEffect } from "react";
import { ComposerResults } from "@/components/ComposerResults";
import { useAuthStore } from "@/lib/store";
import {
  agentsApi,
  profileApi,
  type ResearchData,
  type PageContent,
  type SearchResult,
} from "@/lib/api";
import {
  Send,
  Loader2,
  Compass,
  Mic,
  Upload,
  Link,
  ChevronDown,
  UserRoundPen,
  Heart,
} from "lucide-react";

const CONTENT_TYPES = ["Text", "Image", "Article", "Video", "Ads", "Quiz"] as const;
const PLATFORMS = ["Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube", "Web"] as const;
const LENGTHS = ["Short", "Medium", "Long", "Full Article"] as const;
const TONES = [
  "Casual",
  "Formal",
  "Informative",
  "GenZ",
  "Factual",
  "Hook First",
  "Data Driven",
  "Story Led",
  "Lifestyle"
] as const;

// Welcome lines — one is picked at random and locked for 24h (see effect below).
const GREETINGS = [
  "What should we focus on, {name}?",
  "What's today's agenda, {name}?",
  "Let's jump in, {name}.",
  "What are we creating today, {name}?",
  "How can I help you {name}?",
];

// ── Agent status label ────────────────────────────────────────

// Driven by cumulative milestones, not the transient current_agent / completed
// list. Streaming emits a node's update only AFTER it finishes, and the 2s poll
// can skip the brief composer-running window — so instead we advance the label
// by what data has ARRIVED (queries → research → cards). Each milestone, once
// seen, persists, so the label moves forward monotonically and "Crafting your
// post…" reliably shows for the whole composition step.
function agentStatusLabel(status: string, hasQueries: boolean, hasResearch: boolean): string {
  if (status === "pending") return "Starting up…";
  if (hasResearch) return "Crafting your post…"; // research done → composer running
  if (hasQueries) return "Research agent is searching…"; // personalization done → research running
  return "Personalization agent is thinking…";
}

// MAIN PAGE

export default function CreatePage() {
  const { user } = useAuthStore();
  const [prompt, setPrompt] = useState("");
  const [contentType, setContentType] = useState<string>("Text");
  const [platform, setPlatform] = useState<string>("Twitter");
  const [length, setLength] = useState<string>("Medium");
  const [tone, setTone] = useState<string>("Formal");
  const [nickname, setNickname] = useState<string | null>(null);
  const [greetIdx, setGreetIdx] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState<string>("");
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [agentsCompleted, setAgentsCompleted] = useState<string[]>([]);
  const [personalizationQueries, setPersonalizationQueries] = useState<string[]>([]);
  const [researchData, setResearchData] = useState<ResearchData | null>(null);
  const [composerOutput, setComposerOutput] = useState<any[]>([]);
  const [composerEvidence, setComposerEvidence] = useState<any[]>([]);
  const [composerSources, setComposerSources] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const firstName = user?.full_name?.split(" ")[0] || "Creator";
  const displayName = nickname || firstName;

  // Smart UX State Flag: Detects if any asynchronous output exists below the workspace
  const hasActiveResults = researchData || composerOutput.length > 0 || error;

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

  // Poll run status every 2 seconds until complete or failed
  useEffect(() => {
    if (!runId) return;

    const interval = setInterval(async () => {
      try {
        const res = await agentsApi.getRunStatus(runId);
        setAgentStatus(res.status);
        setCurrentAgent(res.current_agent);
        setAgentsCompleted(res.agents_completed);

        // Milestones arrive mid-run via streaming. Capture them as soon
        // as they appear so the status label advances reliably (instead of
        // depending on catching a transient between 2s polls).
        if (res.personalization_queries?.length > 0) {
          setPersonalizationQueries(res.personalization_queries);
        }
        if (res.research_data) {
          setResearchData(res.research_data);
        }

        if (res.status === "completed") {
          setResearchData(res.research_data);
          setIsGenerating(false);
          setComposerOutput(res.composer_output || []);
          setComposerEvidence(res.composer_evidence || []);
          setComposerSources(res.composer_sources || []);
          clearInterval(interval);
        } else if (res.status === "failed") {
          setError(res.error || "Agent execution failed");
          setIsGenerating(false);
          clearInterval(interval);
        }
      } catch (e: any) {
        setError(e.message);
        setIsGenerating(false);
        clearInterval(interval);
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [runId]);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setIsGenerating(true);
    setError(null);
    setResearchData(null);
    setPersonalizationQueries([]);
    setComposerOutput([]);
    setComposerEvidence([]);
    setComposerSources([]);
    setAgentsCompleted([]);
    setCurrentAgent(null);
    setAgentStatus("pending");

    try {
      const res = await agentsApi.generate({
        prompt,
        content_type: contentType as any,
        platform: platform as any,
        length: length as any,
        tone: tone as any,
      });
      setRunId(res.run_id);
      setAgentStatus(res.status);
      // Sent successfully → the draft is no longer needed.
      try {
        localStorage.removeItem("cupid-prompt-draft");
      } catch {}
    } catch (e: any) {
      setError(e.message);
      setIsGenerating(false);
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
                  {isGenerating ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Send size={14} />
                  )}
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

        {/* Personalization Queries */}
        {personalizationQueries.length > 0 && (
          <PersonalizationQueriesItems queries={personalizationQueries} />
        )}

        {/* Agent Progress Banner */}
        {isGenerating && (
          <div className="mb-5 flex items-center gap-3 rounded-lg bg-(--inline-bg) p-3 px-5 py-2">
            <Heart
              size={14}
              className="animate-heartbeat flex-shrink-0 fill-[var(--color-primary)] text-[var(--color-primary)]"
            />
            <span className="text-sm font-bold text-(--color-input)">
              {agentStatusLabel(agentStatus, personalizationQueries.length > 0, !!researchData)}
            </span>
          </div>
        )}

        {/* Research Results — shows as a milestone as soon as research
                        finishes, then stays (even while the composer runs) */}
        {researchData && <ResearchResults data={researchData} />}

        {/* Composer Output Variants */}
        {composerOutput.length > 0 && !isGenerating && (
          <ComposerResults
            variants={composerOutput}
            evidence={composerEvidence}
            sources={composerSources}
            userName={user?.full_name || "Creator"}
            platform={platform}
            researchImages={(researchData?.fetched_pages ?? [])
              .map((p) => p.image_url)
              .filter((u): u is string => !!u)}
          />
        )}

        <footer className="bg-red fixed right-0 bottom-0 left-0 py-3 text-center text-sm not-italic">
          Cupid can make mistakes, please review post before publishing
        </footer>
      </main>
  );
}

// SELECT DROPDOWN
function SelectDropdown({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
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

// Generated Personalization Queries Span
function PersonalizationQueriesItems({ queries }: { queries: string[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-2 overflow-hidden">
      <button
        onClick={() => setOpen((p) => !p)}
        className="mb-1.5 flex w-full items-center gap-3 rounded-2xl bg-(--color-inline-bg) px-4 py-1.5"
      >
        <UserRoundPen size={14} className="flex-shrink-0 text-[var(--color-primary)]" />
        <span className="flex-1 text-left text-sm font-medium tracking-wide text-(--color-input)">
          Personalized queries generated ✓
        </span>
        <ChevronDown size={14} className="flex-shrink-0 text-[var(--color-primary)]" />
      </button>
      {open && (
        <div className="space-y-2 space-x-2 px-5 py-3">
          {queries.map((q, i) => (
            <span
              key={i}
              className="inline-table rounded-2xl bg-(--color-inline-bg)/50 px-3 py-1 text-sm text-(--color-input)"
            >
              {q}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// RESEARCH RESULTS
function ResearchResults({ data }: { data: ResearchData }) {
  const [open, setOpen] = useState(false);
  const results = data.top_search_results ?? [];
  const pages = data.fetched_pages ?? [];
  const hasResults = results.length > 0 || pages.length > 0;

  return (
    <div className="mb-2 overflow-hidden">
      <button
        onClick={() => setOpen((p) => !p)}
        className="mb-1.5 flex w-full items-center gap-3 rounded-2xl bg-(--color-inline-bg) px-4 py-1.5"
      >
        <Compass size={14} className="flex-shrink-0 text-[var(--color-primary)]" />
        <span className="flex-1 text-left text-sm font-medium tracking-wide text-(--color-input)">
          Research completed: {results.length} Sources ✓
        </span>
        <ChevronDown size={14} className="flex-shrink-0 text-[var(--color-primary)]" />
      </button>

      {!hasResults && (
        <div className="flex items-center gap-2 px-4">
          <Compass size={14} className="flex-shrink-0 text-[var(--color-primary)]" />
          <span className="flex-1 text-left text-sm font-medium tracking-wide text-(--color-grayish-red)">
            No results found ✗ (Try a more specific topic)
          </span>
        </div>
      )}

      {open && pages.length > 0 && (
        <div className="mx-5 overflow-hidden rounded-4xl border border-[var(--color-border)]">
          <div className="divide-y divide-[var(--color-border)]">
            {pages.map((p, i) => (
              <div key={i} className="border-b border-[var(--color-border)] last:border-b-0">
                <SourceCard page={p} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// RESEARCH SOURCE CARD

function SourceCard({ page }: { page: PageContent }) {
  return (
    <div className="overflow-hidden bg-[color-mix(in_srgb,var(--color-inline-bg)_30%,transparent)]">
      <a
        href={page.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex w-full items-center gap-4 p-1"
      >
        {page.image_url && (
          <div className="h-[30px] w-[60px] flex-shrink-0 overflow-hidden rounded-xs bg-[var(--color-inline-bg)]">
            <img
              src={page.image_url}
              alt={page.title}
              className="h-full w-full object-cover"
              onError={(e) => {
                const parent = (e.target as HTMLImageElement).parentElement;
                if (parent) parent.style.display = "none";
              }}
            />
          </div>
        )}
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="flex-shrink-0 text-sm font-medium text-[var(--color-text)]">
            {page.title.split(" ").length > 10
              ? page.title.split(" ").slice(0, 10).join(" ") + "..."
              : page.title}
          </span>
          <span className="flex-1 truncate text-sm font-[var(--font-body)] font-medium text-[var(--color-muted)]">
            {page.domain}
          </span>
        </div>
      </a>
    </div>
  );
}
