"use client";

import { useState, useRef } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuthStore } from "@/lib/store";
import { Send, ChevronLeft, ChevronRight } from "lucide-react";

// ── Dropdown Options ─────────────────────────────────────────

const CONTENT_TYPES = ["Text", "Image", "Article", "Video", "Ads"] as const;
const PLATFORMS = ["All", "Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube"] as const;
const LENGTHS = ["Short", "Medium", "Long"] as const;
const TONES = ["Formal", "Informative", "Casual", "GenZ"] as const;

// ── Mock Recommendations ─────────────────────────────────────

const RECOMMENDATIONS = [
    {
        platform: "twitter",
        author: "You",
        handle: "@you",
        content: "Just shipped a new feature using LangGraph agents. The state machine approach makes complex workflows surprisingly manageable. Thread 🧵",
        likes: 142,
        reposts: 38,
        time: "2h",
    },
    {
        platform: "linkedin",
        author: "You",
        handle: "",
        content: "After 6 months of building with multi-agent systems, here are 5 lessons I wish someone told me on day one.\n\n1. Start with the simplest agent possible\n2. State management > model selection\n3. Evaluation is harder than building\n4. Your persona model IS your moat\n5. Ship weekly, iterate daily",
        likes: 892,
        reposts: 67,
        time: "1d",
    },
    {
        platform: "instagram",
        author: "You",
        handle: "@you",
        content: "Building in public: Day 47 🚀\nOur persona agent can now match your writing style with 94% accuracy. The secret? We treat voice as a high-dimensional embedding, not a prompt template.",
        likes: 2341,
        reposts: 0,
        time: "3h",
    },
    {
        platform: "twitter",
        author: "You",
        handle: "@you",
        content: "Hot take: Most AI-generated social media content fails not because the AI is bad, but because the persona modeling is shallow. Fix the persona, fix the content.",
        likes: 567,
        reposts: 124,
        time: "5h",
    },
    {
        platform: "linkedin",
        author: "You",
        handle: "",
        content: "Hiring for 2 roles on our AI team:\n\n→ ML Engineer (Agent Systems)\n→ Full-Stack Developer (Next.js + FastAPI)\n\nWe're building the future of personalized content. Remote-first, competitive pay, and the chance to work on genuinely hard problems.",
        likes: 1203,
        reposts: 89,
        time: "6h",
    },
    {
        platform: "instagram",
        author: "You",
        handle: "@you",
        content: "The workspace setup where ideas become reality ✨\nMinimalist desk, dual monitors, and a whiteboard full of agent architecture diagrams. This is where the magic happens.",
        likes: 4521,
        reposts: 0,
        time: "12h",
    },
];

// ── Main Page ────────────────────────────────────────────────

export default function CreatePage() {
    const { user } = useAuthStore();
    const [prompt, setPrompt] = useState("");
    const [contentType, setContentType] = useState<string>("Text");
    const [platform, setPlatform] = useState<string>("All");
    const [length, setLength] = useState<string>("Medium");
    const [tone, setTone] = useState<string>("Casual");

    const firstName = user?.full_name?.split(" ")[0] || "Creator";

    const handleGenerate = () => {
        // TODO: Connect to AI agent pipeline
        console.log({ prompt, contentType, platform, length, tone });
    };

    return (
        <ProtectedRoute>
            <main className="min-h-[calc(100vh-60px)] bg-[var(--color-background)] px-6 py-10">
                <div className="max-w-3xl mx-auto">

                    {/* ── Welcome Header ──────────────────────── */}
                    <div className="mb-8 text-center">
                        <h1 className="font-[family-name:var(--font-display)] text-3xl font-normal tracking-tight text-[var(--color-text)] mb-2">
                            What&apos;s on your mind, <em className="text-[var(--color-secondary)]">{firstName}</em>?</h1>
                    </div>

                    {/* ── Input Container with Animated Border ── */}
                    <div className="animated-border mb-12">
                        <div className="animated-border-inner">
                            {/* Textarea */}
                            <textarea
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder="What you want to post?"
                                className="w-full bg-transparent text-[var(--color-text)] font-[family-name:var(--font-body)] text-sm leading-relaxed placeholder:text-[var(--color-muted)] resize-none outline-none"
                                rows={4}
                            />

                            {/* Options Row */}
                            <div className="flex items-center gap-2 flex-wrap">
                                <SelectDropdown label="Type" options={CONTENT_TYPES} value={contentType} onChange={setContentType} />
                                <SelectDropdown label="Platform" options={PLATFORMS} value={platform} onChange={setPlatform} />
                                <SelectDropdown label="Length" options={LENGTHS} value={length} onChange={setLength} />
                                <SelectDropdown label="Tone" options={TONES} value={tone} onChange={setTone} />

                                {/* Send Button */}
                                <button
                                    onClick={handleGenerate}
                                    disabled={!prompt.trim()}
                                    className="btn-primary ml-auto flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                                    style={{ padding: "0.5rem 1rem" }}>
                                    <Send size={14} />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* ── Recommendations ─────────────────────── */}
                    <div>
                        <div className="mb-4">
                            <h2 className="font-[family-name:var(--font-display)] text-xl font-normal text-[var(--color-text)] tracking-tight">
                                Recommendations:
                            </h2>

                        </div>

                        <RecommendationSlider items={RECOMMENDATIONS} />
                    </div>
                </div>
            </main>
        </ProtectedRoute>
    );
}


// ── Select Dropdown Component ────────────────────────────────

function SelectDropdown({
    label,
    options,
    value,
    onChange,
}: {
    label: string;
    options: readonly string[];
    value: string;
    onChange: (val: string) => void;
}) {
    return (
        <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            title={label}
            className="bg-[var(--color-background)] text-[var(--color-text)] border border-[var(--color-border)] rounded-2xl px-2.5 py-1.5 text-xs font-[family-name:var(--font-body)] outline-none cursor-pointer transition-colors hover:border-[var(--color-primary)]"
        >
            {options.map((opt) => (
                <option key={opt} value={opt}>
                    {opt}
                </option>
            ))}
        </select>
    );
}


// ── Recommendation Slider ────────────────────────────────────

function RecommendationSlider({ items }: { items: typeof RECOMMENDATIONS }) {
    const [currentIndex, setCurrentIndex] = useState(0);

    const canGoLeft = currentIndex > 0;
    const canGoRight = currentIndex < items.length - 1;

    const goLeft = () => {
        if (canGoLeft) setCurrentIndex((prev) => prev - 1);
    };

    const goRight = () => {
        if (canGoRight) setCurrentIndex((prev) => prev + 1);
    };

    return (
        <div className="flex items-center gap-4">
            {/* Left Arrow */}
            <button
                onClick={goLeft}
                disabled={!canGoLeft}
                className="flex-shrink-0 w-9 h-9 rounded-full bg-white border border-[var(--color-border)] flex items-center justify-center shadow-sm hover:shadow-md transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
            >
                <ChevronLeft size={16} className="text-[var(--color-text)]" />
            </button>

            {/* Single Card Display */}
            <div className="flex-1 overflow-hidden">
                <div
                    className="flex transition-transform duration-300 ease-in-out"
                    style={{ transform: `translateX(-${currentIndex * 100}%)` }}
                >
                    {items.map((item, i) => (
                        <div key={i} className="w-full flex-shrink-0">
                            <SocialCard {...item} />
                        </div>
                    ))}
                </div>
            </div>

            {/* Right Arrow */}
            <button
                onClick={goRight}
                disabled={!canGoRight}
                className="flex-shrink-0 w-9 h-9 rounded-full bg-white border border-[var(--color-border)] flex items-center justify-center shadow-sm hover:shadow-md transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
            >
                <ChevronRight size={16} className="text-[var(--color-text)]" />
            </button>
        </div>
    );
}



// ── Social Media Cards ───────────────────────────────────────

function SocialCard({
    platform,
    author,
    handle,
    content,
    likes,
    reposts,
    time,
}: (typeof RECOMMENDATIONS)[number]) {
    // Platform-specific styles
    const platformConfig = {
        twitter: {
            label: "𝕏 Post",
            accent: "#1da1f2",
            icon: "𝕏",
        },
        linkedin: {
            label: "LinkedIn Post",
            accent: "#0077b5",
            icon: "in",
        },
        instagram: {
            label: "Instagram Post",
            accent: "#e1306c",
            icon: "📷",
        },
    };

    const config = platformConfig[platform as keyof typeof platformConfig];

    return (
        <div
            className={`flex-shrink-0 w-full my-2 bg-white shadow-md rounded-xl transition-transform hover:scale-102`}
        >
            {/* Card Header */}
            <div className="flex items-center justify-between px-4 pt-4 pb-2">
                <div className="flex items-center gap-2.5">
                    {/* Avatar */}
                    <div
                        className="w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold"
                        style={{ backgroundColor: config.accent }}
                    >
                        {config.icon}
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-[var(--color-text)] font-[family-name:var(--font-body)] leading-tight">
                            {author}
                        </p>
                        {handle && (
                            <p className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
                                {handle}
                            </p>
                        )}
                    </div>
                </div>
                <span className="text-xs text-[var(--color-muted)]">{time}</span>
            </div>

            {/* Card Content */}
            <div className="px-4 py-2">
                <p className="text-sm text-[var(--color-text)] font-[family-name:var(--font-body)] leading-relaxed whitespace-pre-line line-clamp-6">
                    {content}
                </p>
            </div>

            {/* Card Footer */}
            <div className="flex items-center gap-6 px-4 py-3 border-t border-[var(--color-border)] border-opacity-50">
                <span className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
                    ♥ {likes.toLocaleString()}
                </span>
                {reposts > 0 && (
                    <span className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
                        ↻ {reposts.toLocaleString()}
                    </span>
                )}
                <span
                    className="ml-auto text-xs font-medium px-2 py-0.5 rounded-full"
                    style={{ backgroundColor: `${config.accent}15`, color: config.accent }}
                >
                    {config.label}
                </span>
            </div>
        </div>
    );
}
