"use client";

import { useState, useEffect, useRef } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { ComposerResults } from "@/components/ComposerResults";
import { useAuthStore } from "@/lib/store";
import { Send, Loader2, ExternalLink, Compass, Mic, ArrowUpToLine, Link, ChevronDown, UserRoundPen } from "lucide-react";
import { agentsApi, profileApi, type ResearchData, type PageContent, type SearchResult } from "@/lib/api";

const CONTENT_TYPES = ["Text", "Image", "Article", "Video", "Ads", "Poll"] as const;
const PLATFORMS = ["Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube", "Web"] as const;
const LENGTHS = ["Short", "Medium", "Long", "Full Article"] as const;
const TONES = ["Casual", "Formal", "Informative", "GenZ", "Factual", "Hook First", "Data Driven", "Story Led"] as const;

// ── Agent status label ────────────────────────────────────────

function agentStatusLabel(currentAgent: string | null, status: string): string {
    if (status === "pending") return "Starting up…";
    if (currentAgent === "personalization") return "Personalization agent is thinking…";
    if (currentAgent === "research") return "Research agent is searching…";
    if (currentAgent === "composer") return "Crafting your post…";
    return status;
}

// MAIN PAGE

export default function CreatePage() {
    const { user } = useAuthStore();
    const [prompt, setPrompt] = useState("");
    const [contentType, setContentType] = useState<string>("Text");
    const [platform, setPlatform] = useState<string>("Web");
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

                // Show personalization queries as soon as they land
                if (res.personalization_queries?.length > 0) {
                    setPersonalizationQueries(res.personalization_queries);
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
        }, 2000);

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
            <main
                className="min-h-[calc(100vh-60px)] px-6 py-10"
                style={{ backgroundColor: "var(--color-background)" }}
            >
                <div className="max-w-3xl mx-auto">

                    {/* Welcome title */}
                    <div className="mb-8 text-center">
                        <h1 className="font-normal tracking-tight mb-2"
                            style={{
                                fontFamily: "var(--font-display)",
                                fontSize: "clamp(1.6rem, 3vw, 2rem)",
                                color: "var(--color-text)",
                            }}>
                            What&apos;s on your mind,{" "}
                            <em style={{ color: "var(--color-primary)", fontStyle: "italic" }}>
                                {displayName}
                            </em>?
                        </h1>
                    </div>

                    {/* Input Box */}
                    <div className="animated-gradient-border mb-8">
                    <div className="animated-gradient-border-inner relative flex flex-col">
    <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleGenerate();
        }}
        placeholder="What do you want to post about?"
        className="w-full bg-transparent text-sm leading-relaxed resize-none outline-none"
        style={{ fontFamily: "var(--font-body)", color: "var(--color-text)" }}
        rows={4}
    />

    {/* INPUT OPTIONS */}
    <div className="input_options flex items-center justify-between mt-2 gap-2 flex-wrap">
        
        {/* LEFT SIDE */}
        <div className="flex items-center gap-3 flex-wrap min-w-0">
            <SelectDropdown label="Type" options={CONTENT_TYPES} value={contentType} onChange={setContentType} />
            <SelectDropdown label="Platform" options={PLATFORMS} value={platform} onChange={setPlatform} />
            <SelectDropdown label="Length" options={LENGTHS} value={length} onChange={setLength} />
            <SelectDropdown label="Tone" options={TONES} value={tone} onChange={setTone} />

            <ArrowUpToLine size={16} className="cursor-pointer text-gray-500 hover:text-gray-800 transition-colors shrink-0" />
            <Link size={16} className="cursor-pointer text-gray-500 hover:text-gray-800 transition-colors shrink-0" />
        </div>

        {/* RIGHT SIDE */}
        <div className="flex items-center gap-2 ml-auto shrink-0">
            <Mic size={16} className="cursor-pointer text-gray-500 hover:text-gray-800 transition-colors" />

            <button
                onClick={handleGenerate}
                disabled={!prompt.trim() || isGenerating}
                className="btn-primary flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ padding: "0.5rem 1rem" }}
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

                    {/* Error */}
                    {error && (
                        <div className="mb-5 p-4 rounded-lg border-2" style={{
                            backgroundColor: "rgba(239, 68, 68, 0.1)",
                            borderColor: "rgb(239, 68, 68)",
                        }}>
                            <div className="flex items-start gap-3">
                                <span className="text-red-600 text-xl flex-shrink-0">⚠️</span>
                                <div className="flex-1">
                                    <h4 className="font-semibold text-red-700 mb-1" style={{ fontSize: "0.95rem" }}>
                                        Validation Error
                                    </h4>
                                    <p className="text-sm text-red-600 leading-relaxed">
                                        {error}
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Personalization Queries — shown as soon as they arrive */}
                    {personalizationQueries.length > 0 && (
                        <PersonalizationQueriesItems
                            queries={personalizationQueries}
                        />
                    )}

                    {/* Agent Progress Banner */}
                    {isGenerating && (
                        <div className="flex items-center gap-3 mb-5 p-3 rounded-lg px-5 py-2 bg-(--inline-bg)">
                            <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-blue-500" />
                                <span
                                    className="relative inline-flex rounded-full h-2.5 w-2.5"
                                    style={{ backgroundColor: "var(--color-primary)" }}
                                />
                            </span>
                            <span className=" text-xs text-(--color-input) font-bold">
                                {agentStatusLabel(currentAgent, agentStatus)}
                            </span>
                        </div>
                    )}

                    {/* Research Results */}
                    {researchData && !isGenerating && (
                        <ResearchResults data={researchData} />
                    )}

                    {composerOutput.length > 0 && !isGenerating && (
                        <ComposerResults
                            variants={composerOutput}
                            evidence={composerEvidence}
                            sources={composerSources}
                            userName={user?.full_name || "Creator"}
                            platform={platform}
                        />
                    )}

                </div>
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
            className="px-3 py-1 rounded-full bg-[var(--inline-bg)]
    text-[0.8rem] outline-none border-none cursor-pointer"
        >
            {options.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
            ))}
        </select>
    );
}

// Generated Personalization Queries Panel

function PersonalizationQueriesItems({
    queries,
}: {
    queries: string[];
}) {
    const [open, setOpen] = useState(false);

    return (
        <div className="mb-5 rounded-lg overflow-hidden">
            {/* Toggle header */}
            <button
                onClick={() => setOpen((p) => !p)}
                className="w-full flex items-center gap-2.5 px-5 py-2 bg-(--inline-bg)">
                <UserRoundPen size={14} style={{ color: "var(--color-primary)" }} className="flex-shrink-0" />

                <span className="text-xs font-medium tracking-wide flex-1 text-left text-(--color-input)">
                    Personalization agent generated the queries ✓
                </span>

                <ChevronDown
                    size={14}
                    style={{ color: "var(--color-primary)" }}
                    className={`flex-shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
                />
            </button>

            {/* Query list */}
            {open && (
                <div className="px-5 py-3 space-y-2 space-x-2">
                    {queries.map((q, i) => (
                        <span key={i} className="inline-table text-xs px-3 py-1 rounded-lg text-(--color-input) bg-(--inline-bg)">{q}</span>
                    ))}
                </div>
            )}
        </div>
    );
}

// RESEARCH SOURCE CARD

function SourceCard({ page }: { page: PageContent }) {
    return (
        <div className="rounded-xl overflow-hidden bg-[var(--inline-bg)] grid grid-cols-2">
            {page.image_url && (
                <div className="w-full overflow-hidden" style={{ height: "200px", backgroundColor: "var(--color-bg-surface)" }}>
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

            <div className="p-5">
                <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-medium" style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}>
                        {page.domain}
                    </span>
                    <span className="text-xs" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                        {page.text_length.toLocaleString()} chars extracted
                    </span>
                </div>

                <h4
                    className="font-semibold mb-2 leading-snug"
                    style={{ fontSize: "0.95rem", color: "var(--color-text)", fontFamily: "var(--font-body)" }}
                >
                    {page.title}
                </h4>

                <p className="text-xs leading-relaxed mb-4" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                    {page.text_content.substring(0, 400)}{page.text_content.length > 400 ? "…" : ""}
                </p>

                <a
                    href={page.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-medium hover:underline"
                    style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
                >
                    Read full article <ExternalLink size={11} />
                </a>
            </div>
        </div>
    );
}

// RESEARCH RESULTS

function ResearchResults({ data }: { data: ResearchData }) {
    const results = data.top_search_results ?? [];
    const pages = data.fetched_pages ?? [];
    const hasResults = results.length > 0 || pages.length > 0;

    return (
        <div>
            <div
                className="flex items-center gap-3 mb-5 p-3 rounded-lg px-5 py-2 bg-(--inline-bg)">
                <Compass size={14} style={{ color: "var(--color-primary)" }} className="flex-shrink-0" />

                <span className="text-xs font-medium tracking-wide flex-1 text-left text-(--color-input)">
                    Research completed ✓
                </span>
                <span className="ml-auto text-xs text-(--color-input)">{results.length} sources</span>
            </div>

            {/* Empty state */}
            {!hasResults && (
                <>
                    <Compass size={14} style={{ color: "var(--color-primary)" }} className="flex-shrink-0" />

                    <span className="text-xs font-medium tracking-wide flex-1 text-left text-(--color-grayish-red)">
                        No results found ✗ Try a more specific topic.
                    </span>
                </>
            )}

            {/* Fetched Sources */}
            {pages.length > 0 && (
                <div>
                    <p className="text-xs font-medium uppercase tracking-wide mb-3 text-[var(--color-muted)] "                    >
                        Extracted content ({pages.length} pages)
                    </p>
                    <div className="space-y-4">
                        {pages.map((p, i) => (
                            <SourceCard key={i} page={p} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
