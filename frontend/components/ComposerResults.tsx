"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Copy, Check, X, ChevronLeft, ChevronRight, DraftingCompass} from "lucide-react";
import { SocialMediaCard, type Platform } from "@/components/SocialMediaCards";
import { ImagePickerModal } from "@/components/ImagePickerModal";
import { historyApi } from "@/lib/api";

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

// Slider geometry — slide width caps at SLIDE_MAX on desktop but shrinks to fit
// the viewport on mobile so the front card is never clipped. Neighbours peek.
const SLIDE_MAX = 380;
const SLIDE_GAP = 28;

// ─── Main component ─────────────────────────────────────────────

export function ComposerResults({
  variants,
  userName,
  platform,
  historyId,
  researchImages,
}: {
  variants: ComposerVariant[];
  evidence?: DistilledFact[];
  sources?: ComposerSource[];
  userName: string;
  platform: string;
  /** Saved history row id — lets edits persist back to history. */
  historyId?: string | null;
  /** Candidate images (from research pages) for the Image picker. */
  researchImages?: string[];
}) {
  const platformKey = getPlatformKey(platform);

  // Highest-scoring variant first.
  const sorted = useMemo(
    () =>
      [...(variants ?? [])].sort(
        (a, b) => (b.quality?.composite ?? 0) - (a.quality?.composite ?? 0),
      ),
    [variants],
  );

  const [items, setItems] = useState<ComposerVariant[]>(sorted);
  // Per-card chosen media (index-aligned with items).
  const [cardImages, setCardImages] = useState<(string | undefined)[]>([]);

  // current = front/centred card. Edit + Image both act on this card.
  const [current, setCurrent] = useState(0);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  // UI bits
  const [proNote, setProNote] = useState(false);
  const [imageOpen, setImageOpen] = useState(false);

  // Reset on a fresh generation.
  useEffect(() => {
    setItems(sorted);
    setCardImages([]);
    setCurrent(0);
    setEditing(false);
    setDraft("");
  }, [sorted]);

  // Measure the viewport width and the (unscaled) stage height. We keep the card
  // at its full desktop width and scale the whole stage down to fit on mobile, so
  // proportions are identical to desktop — just zoomed out.
  const viewportRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [vw, setVw] = useState(0);
  const [stageH, setStageH] = useState(0);
  useEffect(() => {
    const outer = viewportRef.current;
    const stage = stageRef.current;
    if (!outer || !stage) return;
    const measure = () => {
      setVw(outer.clientWidth);
      setStageH(stage.scrollHeight);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(outer);
    ro.observe(stage);
    return () => ro.disconnect();
  }, []);

  if (!items.length) return null;

  const last = items.length - 1;
  const stride = SLIDE_MAX + SLIDE_GAP;

  // Enough room to show peeking neighbours? On phones we don't — only the front
  // card shows, full and centred; arrows swap which card is in front.
  const peek = vw >= SLIDE_MAX + 100;

  // Desktop: card at full width (scale 1), neighbours peek.
  // Mobile: scale the single card down to fit the viewport (keeps desktop ratio).
  const scale = peek ? 1 : vw > 0 ? Math.min(1, (vw - 16) / SLIDE_MAX) : 1;
  // Stage coordinate space: full viewport for peeking, exactly one card on mobile.
  const internalW = peek ? vw : SLIDE_MAX;
  // Centre the current card. On mobile the stage is one card wide, so neighbours
  // sit fully outside it and get clipped — no peek.
  const trackOffset = peek
    ? vw / 2 - current * stride - SLIDE_MAX / 2
    : -current * stride;

  const goPrev = () => setCurrent((c) => Math.max(0, c - 1));
  const goNext = () => setCurrent((c) => Math.min(last, c + 1));

  const startEdit = () => {
    setDraft(items[current].content);
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setDraft("");
  };

  const saveEdit = async () => {
    const updated = items.map((v, i) =>
      i === current ? { ...v, content: draft, char_count: draft.length } : v,
    );
    setItems(updated);
    setEditing(false);

    if (historyId) {
      setSaving(true);
      try {
        await historyApi.updateVariants(
          historyId,
          updated.map((v) => ({
            angle: v.angle,
            platform: v.platform,
            content: v.content,
            char_count: v.char_count,
          })),
        );
      } catch {
        // Non-fatal: edit still applies locally.
      } finally {
        setSaving(false);
      }
    }
  };

  const onImprove = () => {
    setProNote(true);
    setTimeout(() => setProNote(false), 1800);
  };

  const applyImage = (url: string) => {
    setCardImages((prev) => {
      const next = [...prev];
      next[current] = url;
      return next;
    });
    setImageOpen(false);
  };

  return (
    <div className="space-y-4 mb-15">
      <div
        ref={viewportRef}
        className="overflow-hidden w-full"
        style={{ height: stageH ? stageH * scale : undefined }}
      >
        <div
          ref={stageRef}
          style={{
            width: internalW,
            transform: `scale(${scale})`,
            transformOrigin: "top center",
          }}
        >
          <div
            className="flex items-start"
            style={{
              gap: SLIDE_GAP,
              transform: `translateX(${trackOffset}px)`,
              transition: "transform .35s ease",
            }}
          >
            {items.map((v, i) => (
              <div
                key={i}
                style={{ width: SLIDE_MAX }}
                onClick={() => !editing && i !== current && setCurrent(i)}
              className={`flex-shrink-0 transition-all duration-300 ${
                i === current
                  ? "opacity-100"
                  : "opacity-40 scale-95 cursor-pointer"
              }`}
            >
              {editing && i === current ? (
                <EditCard
                  index={i}
                  draft={draft}
                  saving={saving}
                  onChange={setDraft}
                  onSave={saveEdit}
                  onCancel={cancelEdit}
                />
              ) : (
                <SourceCard
                  variant={v}
                  index={i}
                  selected={i === current}
                  userName={userName}
                  platformKey={platformKey}
                  mediaUrl={cardImages[i]}
                />
              )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center gap-4">
        <button
          onClick={goPrev}
          disabled={current === 0 || editing}
          title="Previous variant"
          className="p-2 rounded-full border border-[var(--color-primary)] text-[var(--color-text)] disabled:opacity-30 transition-colors cursor-pointer disabled:cursor-default"
        >
          <ChevronLeft size={16} />
        </button>

        <span className="text-xs font-medium min-w-[90px] text-center" style={{ color: "var(--color-muted)" }}>
          Variant {current + 1} of {items.length}
        </span>

        <button
          onClick={goNext}
          disabled={current === last || editing}
          title="Next variant"
          className="p-2 rounded-full border border-[var(--color-primary)] text-[var(--color-text)] disabled:opacity-30 transition-colors cursor-pointer disabled:cursor-default"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Action buttons — always one row; smaller on mobile */}
      <div className="relative grid grid-cols-4 gap-1.5 sm:gap-3 w-full text-[11px] sm:text-sm">
        <div className="w-full" title="Require PRO">
          <button disabled className="btn-primary w-full justify-center px-1.5 sm:px-4 whitespace-nowrap opacity-40 cursor-not-allowed pointer-events-none">
            <DraftingCompass size={13} />Improve
          </button>
        </div>
        <button className="btn-secondary w-full justify-center px-1.5 sm:px-4 whitespace-nowrap" onClick={() => setImageOpen(true)}>
          Image
        </button>
        <button
          className="btn-secondary w-full justify-center px-1.5 sm:px-4 whitespace-nowrap disabled:opacity-40"
          onClick={startEdit}
          disabled={editing}
          title="Edit the front variant"
        >
          Edit
        </button>
        <button className="btn-primary w-full justify-center px-1.5 sm:px-4 whitespace-nowrap">Publish</button>

        {/* "Requires Pro" pill for Improve */}
        {proNote && (
          <div className="absolute -top-9 left-0 text-xs font-medium px-3 py-1.5 rounded-md bg-[var(--color-text)] text-white shadow">
            Requires Pro
          </div>
        )}
      </div>

      {imageOpen && (
        <ImagePickerModal
          images={researchImages ?? []}
          onClose={() => setImageOpen(false)}
          onConfirm={applyImage}
        />
      )}
    </div>
  );
}

// ─── Per-source card ─────────────────────────────────────────────

function SourceCard({
  variant,
  index,
  selected,
  userName,
  platformKey,
  mediaUrl,
}: {
  variant: ComposerVariant;
  index: number;
  selected: boolean;
  userName: string;
  platformKey: Platform;
  mediaUrl?: string;
}) {
  const [copied, setCopied] = useState(false);
  const scorePct = Math.round(variant.quality.composite * 100);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(variant.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div
      className="flex flex-col mt-5 bg-[var(--color-inline-bg)] rounded-xl transition-colors border border-[var(--color-border)]">
      {/* Source badge row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 px-4 py-3">
          <span className="text-xs font-semibold text-[var(--color-primary)]">
            Variant {index + 1}
          </span>
          <QualityBadge score={scorePct} />
        </div>
        <div className="flex items-center gap-2 pr-2">
          <button
            onClick={handleCopy}
            title="Copy post"
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors cursor-pointer
              ${copied
                ? "text-[var(--color-primary)] bg-[var(--inline-bg)]"
                : "text-[var(--color-muted)] bg-transparent"
              }`}
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
        mediaUrl={mediaUrl}
      />
    </div>
  );
}

// ─── Edit card (textarea + save/cancel) ─────────────────────────

function EditCard({
  index,
  draft,
  saving,
  onChange,
  onSave,
  onCancel,
}: {
  index: number;
  draft: string;
  saving: boolean;
  onChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="mt-10 w-full rounded-xl border-2 border-[var(--color-primary)] bg-[var(--color-inline-bg)] p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[var(--color-primary)]">
          Editing Variant {index + 1}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onSave}
            disabled={saving || !draft.trim()}
            title="Save"
            className="p-1.5 rounded-md text-green-600 hover:bg-green-50 disabled:opacity-40 transition-colors cursor-pointer disabled:cursor-default"
          >
            <Check size={16} />
          </button>
          <button
            onClick={onCancel}
            disabled={saving}
            title="Cancel"
            className="p-1.5 rounded-md text-red-500 hover:bg-red-50 disabled:opacity-40 transition-colors cursor-pointer disabled:cursor-default"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      <textarea
        value={draft}
        onChange={(e) => onChange(e.target.value)}
        rows={12}
        autoFocus
        className="w-full resize-y rounded-lg border border-[var(--color-border)] bg-white p-3 text-sm leading-relaxed text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
        style={{ fontFamily: "var(--font-body)" }}
      />
      <div className="mt-1 text-right text-[11px]" style={{ color: "var(--color-muted)" }}>
        {draft.length} chars
      </div>
    </div>
  );
}

// ─── Quality score badge ────────────────────────────────────────

function QualityBadge({ score }: { score: number }) {
  const color = score >= 70 ? "#059669" : score >= 45 ? "#d18904" : "#9ca3af";
  return (
    <div
      className="text-xs font-semibold px-2 py-0.5 rounded-full"
      style={{ backgroundColor: `${color}18`, color }}
    >
      {score}%
    </div>
  );
}
