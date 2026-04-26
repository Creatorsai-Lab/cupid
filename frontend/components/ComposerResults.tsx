"use client";

import { useState } from "react";
import { Copy, Check, Sparkles, Hash, ExternalLink } from "lucide-react";
import { SocialMediaCard, type Platform } from "@/components/SocialMediaCards";

// ─── Types ──────────────────────────────────────────────────────

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
  source_rank: number;
  source_domain: string | null;
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

// ─── Platform → card key map ────────────────────────────────────

const PLATFORM_KEY_MAP: Record<string, Platform> = {
  Twitter:   "x",
  LinkedIn:  "linkedin",
  Instagram: "instagram",
  Facebook:  "facebook",
  YouTube:   "youtube",
};

function getPlatformKey(platformName: string): Platform {
  return PLATFORM_KEY_MAP[platformName] ?? "linkedin";
}

// ─── Main component ─────────────────────────────────────────────

export function ComposerResults({
  variants,
  evidence,
  sources,
  userName,
  platform,
}: {
  variants: ComposerVariant[];
  evidence?: DistilledFact[];
  sources?: ComposerSource[];
  userName: string;
  platform: string;
}) {
  if (!variants?.length) return null;

  const platformKey = getPlatformKey(platform);

  return (
    <div className="space-y-4 mb-8">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <Sparkles size={14} style={{ color: "var(--color-primary)" }} />
        <span
          className="text-xs font-medium uppercase tracking-wide"
          style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
        >
          {variants.length} posts · {platform}
        </span>
      </div>

      {/* Social media cards — horizontal scroll row */}
      <div className="flex gap-5 overflow-x-auto pb-4">
        {variants.map((v, i) => (
          <SourceCard key={i} variant={v} userName={userName} platformKey={platformKey} />
        ))}
      </div>

      {/* Evidence + sources (collapsible) */}
      {(evidence?.length || sources?.length) ? (
        <EvidencePanel evidence={evidence ?? []} sources={sources ?? []} />
      ) : null}
    </div>
  );
}

// ─── Per-source card ─────────────────────────────────────────────

function SourceCard({
  variant,
  userName,
  platformKey,
}: {
  variant: ComposerVariant;
  userName: string;
  platformKey: Platform;
}) {
  const [copied, setCopied] = useState(false);
  const scorePct = Math.round(variant.quality.composite * 100);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(variant.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="flex-shrink-0 flex flex-col gap-2">
      {/* Source badge row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-semibold"
            style={{ color: "var(--color-primary)" }}
          >
            Source {variant.source_rank}
          </span>
          {variant.source_domain && (
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: "var(--inline-bg)",
                color: "var(--color-muted)",
              }}
            >
              {variant.source_domain}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <QualityBadge score={scorePct} />
          <button
            onClick={handleCopy}
            title="Copy post"
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors"
            style={{
              color: copied ? "var(--color-primary)" : "var(--color-muted)",
              backgroundColor: copied ? "var(--inline-bg)" : "transparent",
            }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      {/* Platform-accurate social media card */}
      <SocialMediaCard
        platform={platformKey}
        name={userName}
        content={variant.content}
      />
    </div>
  );
}

// ─── Quality score badge ────────────────────────────────────────

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

// ─── Evidence + sources panel (collapsible) ─────────────────────

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
              <p className="text-xs font-medium mb-2" style={{ color: "var(--color-muted)" }}>
                Distilled facts
              </p>
              <ul className="space-y-1.5">
                {evidence.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm" style={{ color: "var(--color-text)" }}>
                    <Hash
                      size={10}
                      className="mt-1 flex-shrink-0"
                      style={{ color: "var(--color-primary)" }}
                    />
                    <span>
                      <span
                        className="text-[10px] uppercase mr-2 px-1.5 py-0.5 rounded"
                        style={{ backgroundColor: "#fff6ed", color: "var(--color-primary)" }}
                      >
                        {f.type}
                      </span>
                      {f.fact}{" "}
                      <span style={{ color: "var(--color-muted)" }}>[S{f.source}]</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {sources.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-2" style={{ color: "var(--color-muted)" }}>
                Sources used
              </p>
              <ul className="space-y-1">
                {sources.map((s, i) => (
                  <li key={i} className="flex items-center gap-1.5 text-sm">
                    <a
                      href={s.url ?? "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                      style={{ color: "var(--color-primary)" }}
                    >
                      [S{i + 1}] {s.title ?? s.url}
                    </a>
                    <ExternalLink size={10} style={{ color: "var(--color-muted)" }} />
                    <span className="text-xs ml-1" style={{ color: "var(--color-muted)" }}>
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
