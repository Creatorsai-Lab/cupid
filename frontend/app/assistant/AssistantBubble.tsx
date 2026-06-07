/**
 * AssistantBubble.tsx — the speech bubble + the tiny input.
 * ════════════════════════════════════════════════════════════════════════
 * Two jobs:
 *   • Show Cia's current line (with an optional "take me there!" button).
 *   • Offer a deliberately SMALL text input — capped so users ask short
 *     questions, matching Cia's short-answer nature.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Send } from "lucide-react";
import type { Bubble } from "./useAssistant";

const MAX_CHARS = 40;

export function AssistantBubble({
  bubble,
  inputOpen,
  onAsk,
  onCloseInput,
}: {
  bubble: Bubble | null;
  inputOpen: boolean;
  onAsk: (text: string) => void;
  onCloseInput: () => void;
}) {
  const router = useRouter();
  const [value, setValue] = useState("");

  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  const tooLong = value.length > MAX_CHARS;

  const submit = () => {
    const text = value.trim();
    if (!text || tooLong) return;
    onAsk(text);
    setValue("");
  };

  if (!bubble && !inputOpen) return null;

  return (
    <div
      className="absolute right-0 bottom-full mb-2 w-56 select-none"
      style={{ fontFamily: "var(--font-body)" }}
    >
      {/* Speech bubble */}
      {bubble && (
        <div
          className="mb-1 rounded-2xl rounded-br-sm border bg-white px-3.5 py-1 shadow-lg"
          style={{ borderColor: "var(--color-border)" }}
        >
          <p className="text-sm leading-snug" style={{ color: "var(--color-text)" }}>
            {bubble.text}
          </p>
          {bubble.navTo && (
            <button
              onClick={() => router.push(bubble.navTo!)}
              className="mt-2 inline-flex items-center gap-1 rounded-full px-1 text-xs font-medium transition-colors"
              style={{ backgroundColor: "var(--color-primary)", color: "#fff" }}
            >
              take me there! <ArrowRight size={11} />
            </button>
          )}
        </div>
      )}

      {/* Tiny input */}
      {inputOpen && (
        <div
          className="py-0.1 flex items-center gap-1.5 rounded-2xl border bg-white px-0.5 text-xs shadow-lg"
          style={{ borderColor: tooLong ? "#ef4444" : "var(--color-border)" }}
        >
          <input
            autoFocus
            value={value}
            maxLength={40}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
              if (e.key === "Escape") onCloseInput();
            }}
            placeholder="ask me briefly..."
            className="flex-1 bg-transparent px-1.5 py-1 text-sm outline-none"
            style={{ color: "var(--color-text)" }}
          />
          <button
            onClick={submit}
            disabled={!value.trim() || tooLong}
            className="rounded-full p-1.5 transition-colors disabled:opacity-30"
            style={{ backgroundColor: "var(--color-primary)", color: "#fff" }}
          >
            <Send size={13} />
          </button>
        </div>
      )}
      {tooLong && (
        <p className="mt-1 text-right text-xs" style={{ color: "#ef4444" }}>
          just {MAX_CHARS} chars please ❤︎
        </p>
      )}
    </div>
  );
}
