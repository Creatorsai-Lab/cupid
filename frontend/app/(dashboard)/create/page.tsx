"use client";

import { useState, useEffect } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuthStore } from "@/lib/store";
import { Send, Loader2, ExternalLink } from "lucide-react";
import { agentsApi, type ResearchData, type PageContent, type SearchResult } from "@/lib/api";

const CONTENT_TYPES = ["Text", "Image", "Article", "Video", "Ads", "Poll"] as const;
const PLATFORMS = ["All", "Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube"] as const;
const LENGTHS = ["Short", "Medium", "Long"] as const;
const TONES = ["Formal", "Informative", "Casual", "GenZ"] as const;

// ── Main Page ────────────────────────────────────────────────

export default function CreatePage() {
    const { user } = useAuthStore();
    const [prompt, setPrompt] = useState("");
    const [contentType, setContentType] = useState<string>("Text");
    const [platform, setPlatform] = useState<string>("All");
    const [length, setLength] = useState<string>("Medium");
    const [tone, setTone] = useState<string>("Casual");

    const [isGenerating, setIsGenerating] = useState(false);
    const [runId, setRunId] = useState<string | null>(null);
    const [agentStatus, setAgentStatus] = useState<string>("");
    const [researchData, setResearchData] = useState<ResearchData | null>(null);
    const [error, setError] = useState<string | null>(null);

    const firstName = user?.full_name?.split(" ")[0] || "Creator";

    // Poll run status every 2 seconds until complete or failed
    useEffect(() => {
        if (!runId) return;

        const interval = setInterval(async () => {
            try {
                const res = await agentsApi.getRunStatus(runId);
                setAgentStatus(res.status);

                if (res.status === "completed") {
                    setResearchData(res.research_data);
                    setIsGenerating(false);
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
                            What&apos;s on your mind,{" "}<em style={{ color: "var(--color-primary)", fontStyle: "italic" }}>{firstName}</em>?
                        </h1>
                    </div>

                    {/* Input Box */}
                    <div className="animated-border mb-8">
                        <div className="animated-border-inner">
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

                            <div className="flex items-center gap-2 flex-wrap">
                                <SelectDropdown label="Type" options={CONTENT_TYPES} value={contentType} onChange={setContentType} />
                                <SelectDropdown label="Platform" options={PLATFORMS} value={platform} onChange={setPlatform} />
                                <SelectDropdown label="Length" options={LENGTHS} value={length} onChange={setLength} />
                                <SelectDropdown label="Tone" options={TONES} value={tone} onChange={setTone} />

                                <button
                                    onClick={handleGenerate}
                                    disabled={!prompt.trim() || isGenerating}
                                    className="btn-primary ml-auto flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                                    style={{ padding: "0.5rem 1rem" }}>
                                    {isGenerating ? (
                                        <>
                                            <Loader2 size={14} className="animate-spin" />
                                            <span className="text-xs capitalize">{agentStatus || "running"}</span>
                                        </>
                                    ) : (
                                        <Send size={14} />
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/*  Error Status */}
                    {error && (
                        <div
                            className="mb-6 p-4 rounded-xl text-sm"
                            style={{
                                backgroundColor: "#fef2f2",
                                border: "1px solid #fecaca",
                                color: "#dc2626",
                                fontFamily: "var(--font-body)",
                            }}
                        >
                            {error}
                        </div>
                    )}

                    {/* Agent Progress Status */}
                    {isGenerating && (
                        <div
                            className="mb-8 flex items-center gap-3 p-4 rounded-xl"
                            style={{ border: "1px solid var(--color-border)", backgroundColor: "white" }}
                        >
                            <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                                <span
                                    className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                                    style={{ backgroundColor: "var(--color-primary)" }}
                                />
                                <span
                                    className="relative inline-flex rounded-full h-2.5 w-2.5"
                                    style={{ backgroundColor: "var(--color-primary)" }}
                                />
                            </span>
                            <span
                                className="text-sm"
                                style={{ fontFamily: "var(--font-body)", color: "var(--color-text)" }}
                            >
                                Research agent is working…
                            </span>
                            <span
                                className="ml-auto text-xs capitalize"
                                style={{ color: "var(--color-muted)" }}
                            >
                                {agentStatus}
                            </span>
                        </div>
                    )}

                    {/* ── Research Results ────────────────────────── */}
                    {researchData && !isGenerating && (
                        <ResearchResults data={researchData} />
                    )}

                </div>
            </main>
        </ProtectedRoute>
    );
}

// ── Select Dropdown ──────────────────────────────────────────

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
            className="border rounded-2xl outline-none cursor-pointer"
            style={{
                backgroundColor: "var(--color-background)",
                color: "var(--color-text)",
                borderColor: "var(--color-border)",
                padding: "0.375rem 0.625rem",
                fontSize: "0.75rem",
                fontFamily: "var(--font-body)",
            }}
        >
            {options.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
            ))}
        </select>
    );
}

// ── Research Results container ───────────────────────────────

function ResearchResults({ data }: { data: ResearchData }) {
    const results = data.top_search_results ?? [];
    const pages = data.fetched_pages ?? [];
    const keywords = data.generated_keywords ?? [];
    const hasResults = results.length > 0 || pages.length > 0;

    return (
        <div>
            {/* Completion banner */}
            <div
                className="flex items-center gap-3 mb-6 p-3 rounded-xl"
                style={{ border: "1px solid #bbf7d0", backgroundColor: "#f0fdf4" }}
            >
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: "#22c55e" }} />
                <span
                    className="text-sm"
                    style={{ fontFamily: "var(--font-body)", color: "#166534" }}
                >
                    Research complete
                </span>
                <span
                    className="ml-auto text-xs"
                    style={{ color: "#16a34a", fontFamily: "var(--font-body)" }}
                >
                    {results.length} sources · {pages.length} pages
                </span>
            </div>

            {/* Keywords */}
            {keywords.length > 0 && (
                <div className="mb-6">
                    <p
                        className="text-xs font-medium uppercase tracking-wide mb-2"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        Searched for
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {keywords.map((kw, i) => (
                            <span
                                key={i}
                                className="px-3 py-1 rounded-full text-xs"
                                style={{
                                    border: "1px solid var(--color-primary)",
                                    backgroundColor: "#fff6ed",
                                    color: "var(--color-primary)",
                                    fontFamily: "var(--font-body)",
                                }}
                            >
                                {kw}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Empty state */}
            {!hasResults && (
                <div
                    className="py-16 text-center rounded-xl"
                    style={{ border: "1px dashed var(--color-border)" }}
                >
                    <p
                        className="text-sm"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        No results found. Try a more specific topic.
                    </p>
                </div>
            )}

            {/* Sources */}
            {results.length > 0 && (
                <div className="mb-8">
                    <p
                        className="text-xs font-medium uppercase tracking-wide mb-3"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        Sources ({results.length})
                    </p>
                    <div className="space-y-2">
                        {results.map((r, i) => (
                            <SourceCard key={i} result={r} />
                        ))}
                    </div>
                </div>
            )}

            {/* Fetched pages */}
            {pages.length > 0 && (
                <div>
                    <p
                        className="text-xs font-medium uppercase tracking-wide mb-3"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        Extracted content ({pages.length} pages)
                    </p>
                    <div className="space-y-4">
                        {pages.map((p, i) => (
                            <PageCard key={i} page={p} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Source Card ──────────────────────────────────────────────

function SourceCard({ result }: { result: SearchResult }) {
    return (
        <a
            href={result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start justify-between gap-3 p-4 rounded-xl transition-shadow hover:shadow-sm"
            style={{ backgroundColor: "white", border: "1px solid var(--color-border)" }}
        >
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                    <span
                        className="text-xs font-medium"
                        style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
                    >
                        {result.domain}
                    </span>
                    <span style={{ color: "var(--color-muted)", fontSize: "0.6rem" }}>·</span>
                    <span
                        className="text-xs"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        score {(result.score ?? 0).toFixed(1)}
                    </span>
                </div>
                <p
                    className="text-sm font-medium mb-1 line-clamp-1"
                    style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
                >
                    {result.title}
                </p>
                <p
                    className="text-xs line-clamp-2 leading-relaxed"
                    style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                >
                    {result.snippet}
                </p>
            </div>
            <ExternalLink size={13} className="flex-shrink-0 mt-0.5" style={{ color: "var(--color-muted)" }} />
        </a>
    );
}

// ── Page Card ────────────────────────────────────────────────

function PageCard({ page }: { page: PageContent }) {
    return (
        <div
            className="rounded-xl overflow-hidden"
            style={{ backgroundColor: "white", border: "1px solid var(--color-border)" }}
        >
            {/* Featured image */}
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

            {/* Text content */}
            <div className="p-5">
                <div className="flex items-center justify-between gap-2 mb-2">
                    <span
                        className="text-xs font-medium"
                        style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
                    >
                        {page.domain}
                    </span>
                    <span
                        className="text-xs"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        {page.text_length.toLocaleString()} chars extracted
                    </span>
                </div>

                <h4
                    className="font-semibold mb-2 leading-snug"
                    style={{ fontSize: "0.95rem", color: "var(--color-text)", fontFamily: "var(--font-body)" }}
                >
                    {page.title}
                </h4>

                <p
                    className="text-xs leading-relaxed mb-4"
                    style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                >
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
