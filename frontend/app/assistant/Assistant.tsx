/**
 * Cia.tsx — the cat herself.
 * ════════════════════════════════════════════════════════════════════════
 * Renders the mood-appropriate gif bottom-right, draggable anywhere, with a
 * close button (dismisses for the session) and a click-to-ask toggle.
 *
 * Mount once in your dashboard layout: <Cia />
 *
 * ASSETS: drop one gif per mood in /public/cia/ named <mood>.gif. Code only
 * references moods, so swapping/expanding gifs never touches this file.
 *   idle.gif · happy.gif · talking.gif · thinking.gif · notify.gif · sleeping.gif
 * (Missing files fall back to idle.gif via onError.)
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { matchInput } from "./matchInput";
import { useAssistant } from "./useAssistant";
import { AssistantBubble } from "./AssistantBubble";
import type { AssistantMood } from "./assistant-knowledge";

const SIZE = 96;            // cat box size in px
const ASSET = (mood: AssistantMood) => `/assistant/${mood}.gif`;

export default function Assistant() {
    const assistant = useAssistant();

    // Position: default bottom-right. Tracked as fixed left/top once dragged.
    const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
    const dragging = useRef(false);
    const moved = useRef(false);
    const offset = useRef({ x: 0, y: 0 });

    // ── Dragging (pointer events: works for mouse + touch) ────────────────
    const onPointerDown = (e: React.PointerEvent) => {
        dragging.current = true;
        moved.current = false;
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        offset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    };

    const onPointerMove = useCallback((e: PointerEvent) => {
        if (!dragging.current) return;
        moved.current = true;
        const x = Math.min(window.innerWidth - SIZE, Math.max(0, e.clientX - offset.current.x));
        const y = Math.min(window.innerHeight - SIZE, Math.max(0, e.clientY - offset.current.y));
        setPos({ x, y });
    }, []);

    const onPointerUp = useCallback(() => { dragging.current = false; }, []);

    useEffect(() => {
        window.addEventListener("pointermove", onPointerMove);
        window.addEventListener("pointerup", onPointerUp);
        return () => {
            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerup", onPointerUp);
        };
    }, [onPointerMove, onPointerUp]);

    // ── Click the cat: toggle input (unless we were dragging) ─────────────
    const onClick = () => {
        if (moved.current) return;     // a drag, not a click
        assistant.wake();
        assistant.setInputOpen(!assistant.inputOpen);
    };

    // ── Ask handler: match input → speak ──────────────────────────────────
    const handleAsk = (text: string) => {
        assistant.setInputOpen(false);
        assistant.say("…", "thinking");                       // brief beat
        setTimeout(() => {
            const reply = matchInput(text, assistant.getLastText());
            assistant.say(reply.text, reply.mood, reply.navTo);
        }, 350);
    };

    if (assistant.dismissed) return null;

    const style: React.CSSProperties = pos
        ? { position: "fixed", left: pos.x, top: pos.y }
        : { position: "fixed", right: 40, bottom: 35 };

    return (
        <div style={{ ...style, width: SIZE, zIndex: 60 }} className="select-none">
            <AssistantBubble
                bubble={assistant.bubble}
                inputOpen={assistant.inputOpen}
                onAsk={handleAsk}
                onCloseInput={() => assistant.setInputOpen(false)}
            />

            <div className="relative group" style={{ width: SIZE, height: SIZE,borderRadius: "50%",background: "radial-gradient(circle at 50% 45%, rgba(146, 141, 137, 0.05) 0%, rgba(145, 142, 138, 0.01) 60%, rgba(255,255,255,0) 75%)",
        filter: "drop-shadow(0 6px 14px rgba(80, 50, 30, 0.20))",
 }}>
                {/* Close button — appears on hover */}
                <button
                    onClick={assistant.dismiss}
                    className="absolute -top-1 -right-1 z-10 w-5 h-5 rounded-full bg-white border flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow"
                    style={{ borderColor: "var(--color-border)", color: "var(--color-destructive)" }}
                    aria-label="Hide Cia"
                >
                    <X size={11} />
                </button>

                {/* The cat */}
                <img
                    src={ASSET(assistant.mood)}
                    alt="Cia"
                    draggable={false}
                    onPointerDown={onPointerDown}
                    onClick={onClick}
                    onError={(e) => { (e.currentTarget as HTMLImageElement).src = ASSET("idle"); }}
                    className="w-full h-full object-contain cursor-grab active:cursor-grabbing drop-shadow-md"
                    style={{ touchAction: "none" }}
                />
            </div>
        </div>
    );
}