"use client";

/**
 * ImagePickerModal — lets the user pick an image for a composed post card.
 *
 * Today it shows images gathered from research pages. The "AI image" button is
 * a placeholder for a future generate-with-AI flow; when that lands, wire it to
 * `lib/aiImage.ts` (which calls our backend — provider keys stay server-side).
 */

import { useState } from "react";
import { X, Check, ImagePlus, Sparkles } from "lucide-react";

export function ImagePickerModal({
  images,
  onClose,
  onConfirm,
}: {
  images: string[];
  onClose: () => void;
  onConfirm: (url: string) => void;
}) {
  const [sel, setSel] = useState<string | null>(null);

  // Dedupe and drop empties.
  const unique = Array.from(new Set(images.filter(Boolean)));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] min-h-[65vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-[var(--color-border)] shadow-xl backdrop-blur-sm"
        style={{ backgroundColor: "color-mix(in srgb, var(--color-background) 95%, transparent)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-2">
          <h2 className="text-md">Pick an image</h2>
          <button
            onClick={onClose}
            title="Close"
            className="cursor-pointer text-[var(--color-primary)] hover:text-[var(--color-text)]"
          >
            <X size={18} />
          </button>
        </div>

        {/* Image grid */}
        <div className="overflow-y-auto p-5">
          {unique.length === 0 ? (
            <p className="py-10 text-center text-sm" style={{ color: "var(--color-muted)" }}>
              No source images found for this topic.
            </p>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {unique.map((url, i) => (
                <button
                  key={i}
                  onClick={() => setSel(url)}
                  className={`relative aspect-video cursor-pointer overflow-hidden rounded-lg border-2 transition-colors ${sel === url ? "border-[var(--color-primary)]" : "border-transparent hover:border-[var(--color-border)]"}`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={url}
                    alt=""
                    className="h-full w-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      const btn = e.currentTarget.closest("button");
                      if (btn) (btn as HTMLElement).style.display = "none";
                    }}
                  />
                  {sel === url && (
                    <div className="absolute inset-0 flex items-center justify-center bg-[var(--color-primary)]/20">
                      <div className="rounded-full bg-[var(--color-primary)] p-1">
                        <Check size={14} className="text-white" />
                      </div>
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4">
          <div className="inline-block" title="Require PRO">
            <button
              disabled
              className="btn-primary pointer-events-none cursor-not-allowed opacity-40"
            >
              <Sparkles size={13} />
              AI image
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="cursor-pointer rounded-md px-3 py-2 text-sm text-[var(--color-muted)] hover:bg-[#fff6ed]"
            >
              Cancel
            </button>
            <button
              onClick={() => sel && onConfirm(sel)}
              disabled={!sel}
              className="btn-secondary flex items-center gap-1.5 disabled:opacity-40"
            >
              <ImagePlus size={14} />
              Use image
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
