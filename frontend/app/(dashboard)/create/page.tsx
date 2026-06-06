"use client";

import { useState, useEffect, useRef } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { ComposerResults } from "@/components/ComposerResults";
import { useAuthStore } from "@/lib/store";
import { Send, Loader2, ExternalLink, Compass, Mic, Upload, Link, ChevronDown, UserRoundPen, Heart } from "lucide-react";
import { agentsApi, profileApi, type ResearchData, type PageContent, type SearchResult } from "@/lib/api";

const CONTENT_TYPES = ["Text", "Image", "Article", "Video", "Ads", "Poll"] as const;
const PLATFORMS = ["Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube", "Web"] as const;
const LENGTHS = ["Short", "Medium", "Long", "Full Article"] as const;
const TONES = ["Casual", "Formal", "Informative", "GenZ", "Factual", "Hook First", "Data Driven", "Story Led"] as const;

// ── Agent status label ────────────────────────────────────────

// Driven by cumulative milestones, not the transient current_agent / completed
// list. Streaming emits a node's update only AFTER it finishes, and the 2s poll
// can skip the brief composer-running window — so instead we advance the label
// by what data has ARRIVED (queries → research → cards). Each milestone, once
// seen, persists, so the label moves forward monotonically and "Crafting your
// post…" reliably shows for the whole composition step.
function agentStatusLabel(
    status: string,
    hasQueries: boolean,
    hasResearch: boolean,
): string {
    if (status === "pending") return "Starting up…";
    if (hasResearch) return "Crafting your post…";      // research done → composer running
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
    const [tone, setTone] = useState<string>("Casual");

    const [nickname, setNickname] = useState<string | null>(null);
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
        profileApi.get().then((res) => {
            if (res.data?.nickname) setNickname(res.data.nickname);
        }).catch(() => {});
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
        } catch (e: any) {
            setError(e.message);
            setIsGenerating(false);
        }
    };

    return (
        <ProtectedRoute>
            <main className={`min-h-[calc(100vh-60px)] max-w-5xl mx-auto flex flex-col transition-all duration-500 ease-in-out ${hasActiveResults ? "justify-start" : "justify-center"}`}>

                    {/* Welcome Title */}
                    <div className="mb-6 text-center">
                        <h1 className="font-normal tracking-tight mb-2 font-[family-name:var(--font-display)] text-[clamp(1.6rem,3.5vw,2.2rem)]">Canvas is your's, {displayName}</h1>
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
                                placeholder="Describe here in detail what you want to create..."
                                className="w-full bg-transparent text-sm leading-relaxed resize-none outline-none mb-4 font-[family-name:var(--font-body)] text-[var(--color-text)]"
                                rows={3}
                            />

                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mt-auto">
                                
                                {/* ROW 1 (Mobile): */}
                                <div className="grid grid-cols-4 md:flex md:items-center gap-1.5 md:gap-2.5 w-full md:w-auto">
                                    <SelectDropdown label="Type" options={CONTENT_TYPES} value={contentType} onChange={setContentType} />
                                    <SelectDropdown label="Platform" options={PLATFORMS} value={platform} onChange={setPlatform} />
                                    <SelectDropdown label="Length" options={LENGTHS} value={length} onChange={setLength} />
                                    <SelectDropdown label="Tone" options={TONES} value={tone} onChange={setTone} />
                                </div>

                                {/* ROW 2 (Mobile): Action Buttons & Icons perfectly aligned */}
                                <div className="flex items-center justify-between md:justify-end gap-4 w-full md:w-auto border-t border-gray-100 md:border-none pt-0 md:pt-0">                                 
                                <div className="flex items-center gap-4 text-(--color-text)">
                                    <Upload size={17} className="cursor-pointer transition-all duration-200 shrink-0 hover:scale-93 hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]" />
                                    <Link size={17} className="cursor-pointer transition-all duration-200 shrink-0 hover:scale-93 hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]" />
                                    <Mic size={17} className="cursor-pointer transition-all duration-200 shrink-0 hover:scale-93 hover:drop-shadow-[-1px_1px_1px_rgba(158,68,38,0.4)]" />
                                </div>
                                    {/* Primary Generation Call Button */}
                                    <button
                                        onClick={handleGenerate}
                                        disabled={!prompt.trim() || isGenerating}
                                        className="btn-primary flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
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
                        <div className="mb-5 p-4 rounded-lg border-1 border-[var(--color-destructive)] bg-[color-mix(in_srgb,var(--color-destructive)_20%,transparent)]">
                            <div className="flex-1">
                                <b className="text-(--color-destructive) mb-1" >Validation Error</b>
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
                        <div className="flex items-center gap-3 mb-5 p-3 rounded-lg px-5 py-2 bg-(--inline-bg)">
                            <Heart
                                size={14}
                                className="flex-shrink-0 animate-heartbeat fill-[var(--color-primary)] text-[var(--color-primary)]"
                            />
                            <span className="text-xs text-(--color-input) font-bold">
                                {agentStatusLabel(agentStatus, personalizationQueries.length > 0, !!researchData)}
                            </span>
                        </div>
                    )}

                    {/* Research Results — shows as a milestone as soon as research
                        finishes, then stays (even while the composer runs) */}
                    {researchData && (
                        <ResearchResults data={researchData} />
                    )}

                    {/* Composer Output Variants */}
                    {composerOutput.length > 0 && !isGenerating && (
                        <ComposerResults
                            variants={composerOutput}
                            evidence={composerEvidence}
                            sources={composerSources}
                            userName={user?.full_name || "Creator"}
                            platform={platform}
                            researchImages={
                                (researchData?.fetched_pages ?? [])
                                    .map((p) => p.image_url)
                                    .filter((u): u is string => !!u)
                            }
                        />
                    )}

                <footer className="fixed bottom-0 left-0 right-0 text-center text-xs not-italic py-3 bg-red">Cupid can make mistakes, please review post before publishing</footer>

            </main>
        </ProtectedRoute>
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
            className="w-full font-[family-name:var(--font-body)] text-(--color-text) text-center bg-(--color-inline-bg) md:text-left px-1 md:px-3 py-1 rounded-full bg-(--color-inline-bg) text-[0.75rem] md:text-[0.8rem] outline-none border-none cursor-pointer truncate"
        >
            {options.map((opt) => (
            <option 
            key={opt} 
            value={opt}
            className="bg-(--color-inline-bg) text-(--color-text) font-sans">
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
                className="w-full flex rounded-2xl items-center mb-1.5 gap-3 px-4 py-1.5 bg-(--color-inline-bg)">
                <UserRoundPen size={14} className="text-[var(--color-primary)] flex-shrink-0" />
                <span className="text-xs font-medium tracking-wide flex-1 text-left text-(--color-input)">
                    Personalized queries generated ✓
                </span>
                <ChevronDown size={14} className="text-[var(--color-primary)] flex-shrink-0" />
            </button>
            {open && (
                <div className="px-5 py-3 space-y-2 space-x-2">
                    {queries.map((q, i) => (
                        <span key={i} className="inline-table text-xs px-3 py-1 rounded-2xl text-(--color-input) bg-(--color-inline-bg)/50">{q}</span>
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
                className="w-full flex rounded-2xl items-center mb-1.5 gap-3 px-4 py-1.5 bg-(--color-inline-bg)">
                <Compass size={14} className="text-[var(--color-primary)] flex-shrink-0" />
                <span className="text-xs font-medium tracking-wide flex-1 text-left text-(--color-input)">
                    Research completed: {results.length} Sources ✓
                </span>
                <ChevronDown size={14} className="text-[var(--color-primary)] flex-shrink-0" />
            </button>

            {!hasResults && (
                <div className="flex items-center gap-2 px-4">
                    <Compass size={14} className="text-[var(--color-primary)] flex-shrink-0" />
                    <span className="text-xs font-medium tracking-wide flex-1 text-left text-(--color-grayish-red)">
                        No results found ✗ (Try a more specific topic)
                    </span>
                </div>
            )}

            {open && pages.length > 0 && (
            <div className="border border-[var(--color-border)] rounded-xl overflow-hidden mx-5">
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
            <a href={page.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-4 p-1 w-full">
            {page.image_url && (
                <div className="w-[60px] h-[30px] overflow-hidden bg-[var(--color-inline-bg)] flex-shrink-0 rounded-xs">
                    <img
                        src={page.image_url}
                        alt={page.title}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                            const parent = (e.target as HTMLImageElement).parentElement;
                            if (parent) parent.style.display = "none";
                        }}
                    />
                </div>
            )}        
            <div className="flex flex-1 items-center gap-3 min-w-0">
                <span className="font-medium text-xs text-[var(--color-text)] flex-shrink-0">
                    {page.title.split(" ").length > 10 
                    ? page.title.split(" ").slice(0, 10).join(" ") + "..." 
                    : page.title}
                </span>
                <span className="text-xs font-medium text-[var(--color-muted)] font-[var(--font-body)] truncate flex-1">
                    {page.domain}
                </span>
            </div>
            </a>
        </div>
    );
}
