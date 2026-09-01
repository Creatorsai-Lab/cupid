"use client";

import { useEffect, useState, useCallback } from "react";
import { History, Trash2, X, Copy, Check, Loader2, AlertCircle, Sparkles } from "lucide-react";
import { historyApi, type HistoryEntry, type HistoryVariant } from "@/lib/api";

export default function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Which entry is open in the modal (null = closed)
  const [activeEntry, setActiveEntry] = useState<HistoryEntry | null>(null);

  // Track which entry is mid-delete so we can disable its button
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const PAGE_SIZE = 20;

  const loadHistory = useCallback(async (offset: number, append: boolean) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await historyApi.list(PAGE_SIZE, offset);
      setEntries((prev) => (append ? [...prev, ...data.entries] : data.entries));
      setTotal(data.total);
      setHasMore(data.has_more);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load history");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadHistory(0, false);
  }, [loadHistory]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this creation from your history?")) return;
    setDeletingId(id);
    try {
      await historyApi.delete(id);
      setEntries((prev) => prev.filter((e) => e.id !== id));
      setTotal((t) => Math.max(0, t - 1));
      // Close modal if the deleted entry was open
      if (activeEntry?.id === id) setActiveEntry(null);
    } catch (err: any) {
      setError(err?.message ?? "Failed to delete entry");
    } finally {
      setDeletingId(null);
    }
  };

  return (
      <main className="mx-auto max-w-5xl p-3 transition-all duration-500">
        <div className="my-8 flex flex-col gap-1">
          <h1 className="text-[clamp(1.8rem, 4vw, 2.2rem)] tracking-tight">Your Chat History</h1>
          <p>
            {total > 0
              ? `${total} saved ${total === 1 ? "history" : "histories"}. Click any card to see the full posts.`
              : "Every post you generate is saved here automatically."}
          </p>
        </div>
        {/* States */}
        {loading && <ListSkeleton />}

        {error && !loading && <ErrorState message={error} onRetry={() => loadHistory(0, false)} />}

        {!loading && !error && entries.length === 0 && <EmptyState />}

        {/* History cards */}
        {!loading && entries.length > 0 && (
          <div className="space-y-4">
            {entries.map((entry) => (
              <HistoryCard
                key={entry.id}
                entry={entry}
                onOpen={() => setActiveEntry(entry)}
                onDelete={() => handleDelete(entry.id)}
                deleting={deletingId === entry.id}
              />
            ))}
          </div>
        )}

        {/* Load more */}
        {hasMore && !loading && (
          <div className="mt-8 flex justify-center">
            <button
              onClick={() => loadHistory(entries.length, true)}
              disabled={loadingMore}
              className="flex items-center gap-2 rounded-md border px-5 py-2 text-sm transition-colors disabled:opacity-50"
              style={{
                borderColor: "var(--color-border)",
                color: "var(--color-text)",
                fontFamily: "var(--font-body)",
              }}
            >
              {loadingMore ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Loading
                </>
              ) : (
                "Load more"
              )}
            </button>
          </div>
        )}
        {/* Detail modal */}
        {activeEntry && <DetailModal entry={activeEntry} onClose={() => setActiveEntry(null)} />}
      </main>
  );
}

// ────────────────────────────────────────────────────────────────
//  History card
// ────────────────────────────────────────────────────────────────

function HistoryCard({
  entry,
  onOpen,
  onDelete,
  deleting,
}: {
  entry: HistoryEntry;
  onOpen: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <div
      className="group relative cursor-pointer rounded-4xl border border-[var(--color-border)] bg-white p-4 transition-all duration-200 ease-in-out hover:border-[var(--color-primary)] hover:shadow-md"
      onClick={onOpen}
    >
      {/* Header: prompt + date + delete */}
      <div className="flex items-start justify-between gap-4">
        <h2 className="line-clamp-2 flex-1 font-[family-name:var(--font-body)] text-base font-semibold text-[var(--color-text)]">
          {entry.prompt}
        </h2>
        <div className="flex flex-shrink-0 items-center gap-3">
          <span className="text-sm whitespace-nowrap text-[var(--color-text)] italic">
            {formatDate(entry.created_at)}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            disabled={deleting}
            className="rounded-md p-1.5 text-[var(--color-destructive)] opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-50 disabled:opacity-50"
            title="Delete"
          >
            {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          </button>
        </div>
      </div>

      {/* Three variant previews */}
      <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
        {entry.variants.slice(0, 3).map((variant, i) => (
          <PreviewCard key={i} variant={variant} />
        ))}
      </div>
    </div>
  );
}

function PreviewCard({ variant }: { variant: HistoryVariant }) {
  return (
    <div className="relative h-[120px] overflow-hidden rounded-4xl border border-[var(--color-border)] bg-[var(--color-background)] p-3">
      <p className="line-clamp-5 text-sm leading-relaxed">{variant.content}</p>
      <div
        className="pointer-events-none absolute right-0 bottom-0 left-0 h-8"
        style={{
          background: "linear-gradient(to bottom, transparent, var(--color-background))",
        }}
      ></div>
    </div>
  );
}

//  Open Detail modal
function DetailModal({ entry, onClose }: { entry: HistoryEntry; onClose: () => void }) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    // Lock body scroll while modal is open
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(42, 37, 32, 0.45)" }}
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white"
        style={{ boxShadow: "var(--shadow-lg, 0 12px 32px rgba(0,0,0,0.15))" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div
          className="flex items-start justify-between gap-4 border-b p-6"
          style={{ borderColor: "var(--color-border)" }}
        >
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles size={13} style={{ color: "var(--color-primary)" }} />
              <span
                className="text-sm font-medium tracking-wide uppercase"
                style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
              >
                {entry.target_platform}
                {entry.tone ? ` · ${entry.tone}` : ""}
                {" · "}
                {formatDate(entry.created_at)}
              </span>
            </div>
            <h2
              className="text-lg leading-snug font-semibold"
              style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
            >
              {entry.prompt}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 rounded-md p-2 hover:bg-[var(--color-background)]"
            style={{ color: "var(--color-muted)" }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal body — 3 full variants */}
        <div className="space-y-4 overflow-y-auto p-6">
          {entry.variants.map((variant, i) => (
            <FullVariant key={i} variant={variant} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

function FullVariant({ variant, index }: { variant: HistoryVariant; index: number }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(variant.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const angleLabel = variant.angle
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return (
    <div className="rounded-4xl border" style={{ borderColor: "var(--color-border)" }}>
      <div
        className="flex items-center justify-between border-b px-4 py-2.5"
        style={{
          borderColor: "var(--color-border)",
          backgroundColor: "var(--color-primary-tint, #fff6ed)",
        }}
      >
        <span
          className="text-sm font-semibold"
          style={{ color: "var(--color-primary)", fontFamily: "var(--font-body)" }}
        >
          Variant {index + 1} · {angleLabel}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm transition-colors"
          style={{
            backgroundColor: copied ? "var(--color-primary-tint, #fff6ed)" : "transparent",
            color: copied ? "var(--color-primary)" : "var(--color-muted)",
          }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <p
        className="p-4 text-sm leading-relaxed whitespace-pre-line"
        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
      >
        {variant.content}
      </p>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Empty / error / skeleton states
// ────────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-8 py-16 text-center"
      style={{ borderColor: "var(--color-border)" }}
    >
      <div
        className="mb-4 flex h-12 w-12 items-center justify-center rounded-full"
        style={{ backgroundColor: "var(--color-primary-tint, #fff6ed)" }}
      >
        <History size={20} style={{ color: "var(--color-primary)" }} />
      </div>
      <h3
        className="mb-2 text-base font-medium"
        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
      >
        No creations yet
      </h3>
      <p
        className="mb-5 max-w-md text-sm"
        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
      >
        Head to the Create page and generate your first set of posts. They'll show up here
        automatically.
      </p>
      <a
        href="/create"
        className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm text-white"
        style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}
      >
        Start creating
      </a>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <AlertCircle size={28} className="mb-3 text-red-400" />
      <p
        className="mb-1 text-sm font-medium"
        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
      >
        Could not load history
      </p>
      <p
        className="mb-4 max-w-sm text-sm"
        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
      >
        {message}
      </p>
      <button
        onClick={onRetry}
        className="flex items-center gap-2 rounded-md px-4 py-2 text-sm text-white"
        style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}
      >
        Try again
      </button>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="animate-pulse rounded-2xl border bg-white p-6"
          style={{ borderColor: "var(--color-border)" }}
        >
          <div className="mb-4 h-5 w-2/3 rounded bg-[var(--color-primary-tint,#fff6ed)]" />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {[0, 1, 2].map((j) => (
              <div key={j} className="h-36 rounded-4xl bg-[var(--color-primary-tint,#fff6ed)]" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Helpers
// ────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  // "2026-05-23..." → "23-05-26" to match the screenshot's DD-MM-YY
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yy = String(d.getFullYear()).slice(-2);
  return `${dd}-${mm}-${yy}`;
}
