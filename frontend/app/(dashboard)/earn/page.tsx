"use client";

import { useEffect, useState, useCallback } from "react";
import {
    CircleDollarSign, Sparkles, TrendingUp, Lightbulb, ArrowRight,
    Check, Loader2, AlertCircle, Lock, Target, Wrench, ExternalLink, Users, Eye, FileText,
} from "lucide-react";
import { earnApi, type EarnQuestion, type ReadinessResponse, type StreamCard } from "@/lib/api";
import ProtectedRoute from "@/components/ProtectedRoute";

/* ────────────────────────────────────────────────────────────────────────
   /earn — the monetization coach.
   Two top-level states:
     • No profile yet  → the mandatory Q&A gate.
     • Profile exists  → the four-section readiness dashboard.
   ──────────────────────────────────────────────────────────────────────── */

export default function EarnPage() {
    const [checking, setChecking] = useState(true);
    const [hasProfile, setHasProfile] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const checkProfile = useCallback(async () => {
        setChecking(true);
        setError(null);
        try {
            const p = await earnApi.getProfile();
            setHasProfile(p.exists);
        } catch (e: any) {
            setError(e?.message ?? "Could not load the Earn page");
        } finally {
            setChecking(false);
        }
    }, []);

    useEffect(() => { checkProfile(); }, [checkProfile]);

    return (
        <ProtectedRoute>
            <main className="min-h-[calc(100vh-60px)] px-6 py-10" style={{ backgroundColor: "var(--color-background)" }}>
                <div className="max-w-4xl mx-auto">
                    {checking && <CenterSpinner label="Loading your earning profile…" />}
                    {error && !checking && <ErrorState message={error} onRetry={checkProfile} />}
                    {!checking && !error && !hasProfile && <QAGate onComplete={() => setHasProfile(true)} />}
                    {!checking && !error && hasProfile && <Dashboard />}
                </div>
            </main>
        </ProtectedRoute>
    );
}

/* ════════════════════════════════════════════════════════════════════════
   THE MANDATORY Q&A GATE
   ════════════════════════════════════════════════════════════════════════ */

function QAGate({ onComplete }: { onComplete: () => void }) {
    const [questions, setQuestions] = useState<EarnQuestion[]>([]);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [err, setErr] = useState<string | null>(null);

    useEffect(() => {
        (async () => {
            try {
                const r = await earnApi.getQuestions();
                setQuestions(r.questions);
            } catch (e: any) {
                setErr(e?.message ?? "Could not load questions");
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    const allAnswered = questions.length > 0 && questions.every((q) => answers[q.stream_id]);

    const submit = async () => {
        if (!allAnswered) return;
        setSubmitting(true);
        setErr(null);
        try {
            await earnApi.submitProfile(answers);
            onComplete();
        } catch (e: any) {
            setErr(e?.message ?? "Could not save your answers");
            setSubmitting(false);
        }
    };

    if (loading) return <CenterSpinner label="Preparing a few quick questions…" />;

    return (
        <div className="max-w-2xl mx-auto">
            <header className="mb-8 text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-4"
                     style={{ backgroundColor: "var(--color-primary-tint, #fff6ed)" }}>
                    <CircleDollarSign size={22} style={{ color: "var(--color-primary)" }} />
                </div>
                <h1 className="font-normal tracking-tight mb-2"
                    style={{ fontFamily: "var(--font-display)", fontSize: "clamp(1.7rem,3vw,2.2rem)", color: "var(--color-text)" }}>
                    Let's map your <em style={{ color: "var(--color-primary)", fontStyle: "italic" }}>earning paths</em>
                </h1>
                <p className="text-sm max-w-md mx-auto" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                    A few quick questions so we can tailor everything to you. There are no wrong answers —
                    just tell us where you stand with each.
                </p>
            </header>

            <div className="space-y-4">
                {questions.map((q, i) => (
                    <div key={q.stream_id} className="rounded-2xl border bg-white p-5"
                         style={{ borderColor: "var(--color-border)" }}>
                        <p className="text-sm font-medium mb-3 flex gap-2"
                           style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}>
                            <span style={{ color: "var(--color-primary)" }}>{i + 1}.</span>
                            {q.question}
                        </p>
                        <div className="grid grid-cols-3 gap-2">
                            {q.options.map((opt) => {
                                const active = answers[q.stream_id] === opt.value;
                                return (
                                    <button key={opt.value}
                                        onClick={() => setAnswers((a) => ({ ...a, [q.stream_id]: opt.value }))}
                                        className="text-xs px-3 py-2.5 rounded-lg border transition-all text-center leading-tight"
                                        style={{
                                            borderColor: active ? "var(--color-primary)" : "var(--color-border)",
                                            backgroundColor: active ? "var(--color-primary)" : "transparent",
                                            color: active ? "#fff" : "var(--color-text)",
                                            fontFamily: "var(--font-body)",
                                        }}>
                                        {opt.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </div>

            {err && <p className="text-xs text-red-500 mt-4 text-center">{err}</p>}

            <div className="sticky bottom-4 mt-6">
                <button onClick={submit} disabled={!allAnswered || submitting}
                    className="w-full flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-white text-sm font-medium transition-all disabled:opacity-40 shadow-lg"
                    style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}>
                    {submitting ? <Loader2 size={16} className="animate-spin" />
                        : <>Show my earning plan <ArrowRight size={16} /></>}
                </button>
                {!allAnswered && (
                    <p className="text-center text-xs mt-2" style={{ color: "var(--color-muted)" }}>
                        Answer all {questions.length} to continue
                    </p>
                )}
            </div>
        </div>
    );
}

/* ════════════════════════════════════════════════════════════════════════
   THE FOUR-SECTION DASHBOARD
   ════════════════════════════════════════════════════════════════════════ */

function Dashboard() {
    const [data, setData] = useState<ReadinessResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true); setErr(null);
        try {
            setData(await earnApi.getReadiness());
        } catch (e: any) {
            setErr(e?.message ?? "Could not build your plan");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    if (loading) return <CenterSpinner label="Building your personalized plan…" />;
    if (err) return <ErrorState message={err} onRetry={load} />;
    if (!data) return null;

    return (
        <div className="space-y-10">
            <SectionStats stats={data.stats} />
            <SectionVerdict verdict={data.verdict} />
            <SectionOpportunities opp={data.opportunities} />
            <SectionCreative creative={data.creative} />
        </div>
    );
}

/* ── Section 1 — Stats snapshot ──────────────────────────────────────── */

function SectionStats({ stats }: { stats: ReadinessResponse["stats"] }) {
    const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K` : `${n}`;
    return (
        <section>
            <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
            <div>
                <h1 className="tracking-tight text-[clamp(1.8rem, 4vw, 2.2rem)]">Your Monitization Coach</h1>
            </div>
                <span className="text-xs px-3 py-1.5 rounded-full font-medium border border-[var(--color-primary)] text-[var(--color-primary)] font-[family-name:var(--font-body)]">{stats.tier_label}</span>
            </div>
            <div className="grid grid-cols-3 gap-3 mb-3">
                <StatTile icon={<Users size={15} />} label="Followers" value={fmt(stats.total_followers)} />
                <StatTile icon={<Eye size={15} />} label="Monthly views" value={fmt(stats.monthly_views)} />
                <StatTile icon={<FileText size={15} />} label="Posts" value={fmt(stats.total_posts)} />
            </div>

            <p className="text-sm px-1" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                {stats.tier_blurb}
                {stats.confidence === "low" && (
                    <span className="block mt-1 text-xs italic">
                        Based on your connected accounts — connect more for sharper guidance.
                    </span>
                )}
            </p>
        </section>
    );
}

function StatTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
    return (
        <div className="rounded-2xl border bg-white p-4" style={{ borderColor: "var(--color-border)" }}>
            <div className="flex items-center gap-1.5 mb-1" style={{ color: "var(--color-muted)" }}>
                {icon}<span className="text-xs" style={{ fontFamily: "var(--font-body)" }}>{label}</span>
            </div>
            <div className="text-2xl font-semibold" style={{ color: "var(--color-text)", fontFamily: "var(--font-display)" }}>
                {value}
            </div>
        </div>
    );
}

/* ── Section 2 — Eligibility verdict ─────────────────────────────────── */

function SectionVerdict({ verdict }: { verdict: ReadinessResponse["verdict"] }) {
    return (
        <section>
            {/* Coach summary */}
            <div className="rounded-2xl p-5 mb-5 border"
                 style={{ backgroundColor: "var(--color-primary-tint, #fff6ed)", borderColor: "var(--color-border)" }}>
                <div className="flex items-center gap-2 mb-2">
                    <Sparkles size={14} style={{ color: "var(--color-primary)" }} />
                    <span className="text-xs uppercase tracking-wide font-semibold"
                          style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}>
                        Your coach's read
                    </span>
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}>
                    {verdict.coach_summary}
                </p>
            </div>

            {verdict.green_lights.length > 0 && (
                <CardGroup title="You're cleared for these" icon={<Check size={15} />} accent>
                    {verdict.green_lights.map((c) => <StreamRow key={c.stream_id} card={c} />)}
                </CardGroup>
            )}
            {verdict.almost_there.length > 0 && (
                <CardGroup title="Almost within reach" icon={<Target size={15} />}>
                    {verdict.almost_there.map((c) => <StreamRow key={c.stream_id} card={c} />)}
                </CardGroup>
            )}
            {verdict.optimizing.length > 0 && (
                <CardGroup title="Already doing — let's sharpen these" icon={<Wrench size={15} />}>
                    {verdict.optimizing.map((c) => <StreamRow key={c.stream_id} card={c} />)}
                </CardGroup>
            )}
            {verdict.foundation.length > 0 && (
                <CardGroup title="Grow toward these" icon={<Lock size={15} />}>
                    {verdict.foundation.map((c) => <StreamRow key={c.stream_id} card={c} />)}
                </CardGroup>
            )}
        </section>
    );
}

function CardGroup({ title, icon, accent, children }: {
    title: string; icon: React.ReactNode; accent?: boolean; children: React.ReactNode;
}) {
    return (
        <div className="mb-5">
            <div className="flex items-center gap-2 mb-2 px-1"
                 style={{ color: accent ? "var(--color-primary)" : "var(--color-muted)" }}>
                {icon}
                <h3 className="text-sm font-semibold" style={{ fontFamily: "var(--font-body)" }}>{title}</h3>
            </div>
            <div className="space-y-2">{children}</div>
        </div>
    );
}

function StreamRow({ card }: { card: StreamCard }) {
    return (
        <div className="rounded-xl border bg-white p-4" style={{ borderColor: "var(--color-border)" }}>
            <div className="flex items-start justify-between gap-3 mb-1">
                <h4 className="text-sm font-semibold" style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}>
                    {card.label}
                </h4>
                {card.followers_gap > 0 && (
                    <span className="text-xs whitespace-nowrap px-2 py-0.5 rounded-full"
                          style={{ backgroundColor: "var(--color-background)", color: "var(--color-muted)" }}>
                        {card.followers_gap.toLocaleString()} to go
                    </span>
                )}
            </div>
            <p className="text-xs mb-2 leading-relaxed" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                {card.short_pitch}
            </p>
            <p className="text-xs italic" style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}>
                {card.tradeoff_label}
            </p>
        </div>
    );
}

/* ── Section 3 — Matched opportunities ───────────────────────────────── */

function SectionOpportunities({ opp }: { opp: ReadinessResponse["opportunities"] }) {
    return (
        <section>
            <SectionHeader icon={<TrendingUp size={18} />} title="Opportunities for you" />
            <p className="text-sm mb-4 px-1" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                {opp.intro}
            </p>
            {opp.opportunities.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {opp.opportunities.map((o) => (
                        <a key={o.id} href={o.url} target="_blank" rel="noopener noreferrer"
                           className="rounded-2xl border bg-white p-5 transition-shadow hover:shadow-md group"
                           style={{ borderColor: "var(--color-border)" }}>
                            <div className="flex items-start justify-between gap-2 mb-1">
                                <h4 className="text-sm font-semibold" style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}>
                                    {o.title}
                                </h4>
                                <ExternalLink size={14} className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                                              style={{ color: "var(--color-primary)" }} />
                            </div>
                            {o.description && (
                                <p className="text-xs mb-2 leading-relaxed line-clamp-2"
                                   style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                                    {o.description}
                                </p>
                            )}
                            <div className="flex items-center gap-2">
                                <span className="text-xs px-2 py-0.5 rounded-full capitalize"
                                      style={{ backgroundColor: "var(--color-primary-tint, #fff6ed)", color: "var(--color-primary)" }}>
                                    {o.opp_type.replace("_", " ")}
                                </span>
                                {o.commission_note && (
                                    <span className="text-xs" style={{ color: "var(--color-muted)" }}>{o.commission_note}</span>
                                )}
                            </div>
                        </a>
                    ))}
                </div>
            ) : (
                <div className="rounded-2xl border-2 border-dashed p-8 text-center"
                     style={{ borderColor: "var(--color-border)" }}>
                    <p className="text-sm max-w-md mx-auto" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                        {opp.empty_message}
                    </p>
                </div>
            )}
        </section>
    );
}

/* ── Section 4 — Creative niche ideas ────────────────────────────────── */

function SectionCreative({ creative }: { creative: ReadinessResponse["creative"] }) {
    return (
        <section>
            <SectionHeader icon={<Lightbulb size={18} />} title="Creative ideas for your niche" />
            <p className="text-sm mb-4 px-1" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                {creative.intro}
            </p>
            <div className="space-y-3">
                {creative.ideas.map((idea, i) => (
                    <div key={i} className="rounded-2xl border bg-white p-5 flex gap-4" style={{ borderColor: "var(--color-border)" }}>
                        <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold"
                             style={{ backgroundColor: "var(--color-primary-tint, #fff6ed)", color: "var(--color-primary)", fontFamily: "var(--font-display)" }}>
                            {i + 1}
                        </div>
                        <div>
                            <h4 className="text-sm font-semibold mb-1" style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}>
                                {idea.title}
                            </h4>
                            <p className="text-sm leading-relaxed" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                                {idea.idea}
                            </p>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}

/* ── Shared bits ─────────────────────────────────────────────────────── */

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
    return (
        <div className="flex items-center gap-2 mb-1">
            <span style={{ color: "var(--color-primary)" }}>{icon}</span>
            <h2 className="font-normal tracking-tight"
                style={{ fontFamily: "var(--font-display)", fontSize: "1.4rem", color: "var(--color-text)" }}>
                {title}
            </h2>
        </div>
    );
}

function CenterSpinner({ label }: { label: string }) {
    return (
        <div className="flex flex-col items-center justify-center py-24">
            <Loader2 size={26} className="animate-spin mb-3" style={{ color: "var(--color-primary)" }} />
            <p className="text-sm" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>{label}</p>
        </div>
    );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center py-24 text-center">
            <AlertCircle size={26} className="text-red-400 mb-3" />
            <p className="text-sm mb-4 max-w-sm" style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>{message}</p>
            <button onClick={onRetry} className="px-4 py-2 text-sm rounded-md text-white"
                    style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}>
                Try again
            </button>
        </div>
    );
}