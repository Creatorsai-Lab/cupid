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
        className="rounded-2xl max-w-4xl w-full max-h-[90vh] min-h-[65vh] flex flex-col overflow-hidden border border-[var(--color-border)] shadow-xl backdrop-blur-sm"
        style={{ backgroundColor: "color-mix(in srgb, var(--color-background) 95%, transparent)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-2 border-b border-[var(--color-border)]">
          <h2 className="text-md">Pick an image</h2>
          <button
            onClick={onClose}
            title="Close"
            className="text-[var(--color-primary)] hover:text-[var(--color-text)] cursor-pointer">
            <X size={18} />
          </button>
        </div>

        {/* Image grid */}
        <div className="p-5 overflow-y-auto">
          {unique.length === 0 ? (
            <p className="text-sm text-center py-10" style={{ color: "var(--color-muted)" }}>
              No source images found for this topic.
            </p>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {unique.map((url, i) => (
                <button
                  key={i}
                  onClick={() => setSel(url)}
                  className={`relative aspect-video rounded-lg overflow-hidden border-2 transition-colors cursor-pointer
                    ${sel === url ? "border-[var(--color-primary)]" : "border-transparent hover:border-[var(--color-border)]"}`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={url}
                    alt=""
                    className="w-full h-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      const btn = e.currentTarget.closest("button");
                      if (btn) (btn as HTMLElement).style.display = "none";
                    }}
                  />
                  {sel === url && (
                    <div className="absolute inset-0 bg-[var(--color-primary)]/20 flex items-center justify-center">
                      <div className="bg-[var(--color-primary)] rounded-full p-1">
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
          <button disabled className="btn-primary opacity-40 cursor-not-allowed pointer-events-none">
            <Sparkles size={13} />AI image
          </button>
          </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onClose}
            className="text-xs px-3 py-2 rounded-md text-[var(--color-muted)] hover:bg-[#fff6ed] cursor-pointer"
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
