"use client";

import { useState } from "react";
import { Copy, Check, Sparkles, TrendingUp, BookOpen, Hash, Zap } from "lucide-react";

// ─── Types (mirror backend state) ────────────────────────────

export interface QualityBreakdown {
  composite: number;
  length_fit: number;
  grounding: number;
  persona_match: number;
  hook_strength: number;
  passes: boolean;
}

export interface ComposerVariant {
  angle: "hook_first" | "data_driven" | "story_led";
  platform: string;
  content: string;
  hashtags: string[];
  char_count: number;
  quality: QualityBreakdown;
}

export interface DistilledFact {
  fact: string;
  source: number;
  type: "stat" | "quote" | "entity" | "claim" | "relationship";
}

export interface ComposerSource {
  title: string | null;
  url: string | null;
  domain: string | null;
  rank_score: number | null;
}

// ─── Angle metadata ──────────────────────────────────────────

const ANGLE_META: Record<
  ComposerVariant["angle"],
  { label: string; icon: typeof Zap; tagline: string; tint: string }
> = {
  hook_first:  { label: "Hook First",  icon: Zap,         tagline: "Attention-grabbing opener", tint: "#d47a03" },
  data_driven: { label: "Data Driven", icon: TrendingUp,  tagline: "Leads with the number",     tint: "#0a66c2" },
  story_led:   { label: "Story Led",   icon: BookOpen,    tagline: "Human moment first",        tint: "#7c3aed" },
};

// ─── Main component ─────────────────────────────────────────

export function ComposerResults({
  variants,
  evidence,
  sources,
}: {
  variants: ComposerVariant[];
  evidence?: DistilledFact[];
  sources?: ComposerSource[];
}) {
  if (!variants?.length) return null;

  return (
    <div className="space-y-4 mb-8">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <Sparkles size={14} style={{ color: "var(--color-primary)" }} />
        <span
          className="text-xs font-medium uppercase tracking-wide"
          style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
        >
          Composer Agent — {variants.length} Variants Ready
        </span>
      </div>

      {/* Variant cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {variants.map((v, i) => (
          <VariantCard key={i} variant={v} />
        ))}
      </div>

      {/* Evidence + sources (collapsible) */}
      {(evidence?.length || sources?.length) ? (
        <EvidencePanel evidence={evidence ?? []} sources={sources ?? []} />
      ) : null}
    </div>
  );
}

// ─── Variant card ────────────────────────────────────────────

function VariantCard({ variant }: { variant: ComposerVariant }) {
  const [copied, setCopied] = useState(false);
  const meta = ANGLE_META[variant.angle];
  const Icon = meta.icon;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(variant.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const scorePct = Math.round(variant.quality.composite * 100);

  return (
    <div
      className="rounded-xl overflow-hidden bg-white border flex flex-col"
      style={{ borderColor: "var(--color-border)" }}
    >
      {/* Card header */}
      <div
        className="flex items-center justify-between px-4 py-2.5 border-b"
        style={{ borderColor: "var(--color-border)", backgroundColor: `${meta.tint}10` }}
      >
        <div className="flex items-center gap-2">
          <Icon size={14} style={{ color: meta.tint }} />
          <div>
            <p className="text-xs font-semibold" style={{ color: meta.tint }}>
              {meta.label}
            </p>
            <p className="text-[10px]" style={{ color: "var(--color-muted)" }}>
              {meta.tagline}
            </p>
          </div>
        </div>
        <QualityBadge score={scorePct} />
      </div>

      {/* Content body */}
      <div className="p-4 flex-1 flex flex-col">
        <p
          className="text-sm leading-relaxed whitespace-pre-line flex-1"
          style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
        >
          {variant.content}
        </p>

        {/* Meta row */}
        <div
          className="flex items-center justify-between mt-4 pt-3 border-t text-xs"
          style={{ borderColor: "var(--color-border)", color: "var(--color-muted)" }}
        >
          <span>
            {variant.char_count} chars · {variant.platform}
          </span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-colors"
            style={{
              backgroundColor: copied ? "#d47a0315" : "transparent",
              color: copied ? "#d47a03" : "var(--color-muted)",
            }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Quality score badge ────────────────────────────────────

function QualityBadge({ score }: { score: number }) {
  const color = score >= 70 ? "#059669" : score >= 45 ? "#d47a03" : "#9ca3af";
  return (
    <div
      className="text-xs font-semibold px-2 py-0.5 rounded-full"
      style={{ backgroundColor: `${color}18`, color }}
    >
      {score}%
    </div>
  );
}

// ─── Evidence + sources panel ───────────────────────────────

function EvidencePanel({
  evidence,
  sources,
}: {
  evidence: DistilledFact[];
  sources: ComposerSource[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="rounded-xl bg-white border overflow-hidden"
      style={{ borderColor: "var(--color-border)" }}
    >
      <button
        onClick={() => setOpen((p) => !p)}
        className="w-full flex items-center justify-between px-4 py-2.5"
        style={{
          backgroundColor: "#fff6ed",
          borderBottom: open ? "1px solid var(--color-border)" : "none",
        }}
      >
        <span
          className="text-xs font-medium uppercase tracking-wide"
          style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
        >
          Evidence: {evidence.length} facts · {sources.length} sources
        </span>
        <span
          className="text-xs transition-transform"
          style={{
            color: "var(--color-primary)",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
          }}
        >
          ⌄
        </span>
      </button>

      {open && (
        <div className="p-4 space-y-4">
          {evidence.length > 0 && (
            <div>
              <p
                className="text-xs font-medium mb-2"
                style={{ color: "var(--color-muted)" }}
              >
                Distilled facts
              </p>
              <ul className="space-y-1.5">
                {evidence.map((f, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm"
                    style={{ color: "var(--color-text)" }}
                  >
                    <Hash
                      size={10}
                      className="mt-1 flex-shrink-0"
                      style={{ color: "var(--color-primary)" }}
                    />
                    <span>
                      <span
                        className="text-[10px] uppercase mr-2 px-1.5 py-0.5 rounded"
                        style={{
                          backgroundColor: "#fff6ed",
                          color: "var(--color-primary)",
                        }}
                      >
                        {f.type}
                      </span>
                      {f.fact}{" "}
                      <span style={{ color: "var(--color-muted)" }}>
                        [S{f.source}]
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {sources.length > 0 && (
            <div>
              <p
                className="text-xs font-medium mb-2"
                style={{ color: "var(--color-muted)" }}
              >
                Sources used
              </p>
              <ul className="space-y-1">
                {sources.map((s, i) => (
                  <li key={i} className="text-sm">
                    <a
                      href={s.url ?? "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                      style={{ color: "var(--color-primary)" }}
                    >
                      [S{i + 1}] {s.title ?? s.url}
                    </a>
                    <span
                      className="text-xs ml-2"
                      style={{ color: "var(--color-muted)" }}
                    >
                      {s.domain}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}