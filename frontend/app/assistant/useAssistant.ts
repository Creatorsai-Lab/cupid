/**
 * useAssistant.ts — Cia's session state (in-memory only, resets on reload).
 * ════════════════════════════════════════════════════════════════════════
 *
 * Holds: whether she's dismissed, her screen position, her current mood, and
 * the active speech bubble. Exposes the actions the components call.
 *
 * THE notify() SEAM
 * ─────────────────
 * `notify(message, mood)` is the single entry point for making Cia pop a
 * bubble. TODAY: your pages call it directly from events you already have
 * ("post ready!"). LATER: a tiny poller can call this same method with
 * server-fetched nudges — so adding backend notifications touches only the
 * poller, never Cia herself. That's the whole reason this is one method.
 *
 * Exposed globally (window.assistant) so any page can call assistant.notify(...)
 * without prop-drilling. Lightweight and good enough for a session buddy.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { GREETINGS, IDLE_POKES, type AssistantMood } from "./assistant-knowledge";


export interface Bubble {
    text: string;
    navTo?: string;
}

const BUBBLE_MS = 6000;          // how long a bubble lingers
const IDLE_MS = 45_000;          // inactivity before an idle poke

export function useAssistant() {
    const [dismissed, setDismissed] = useState(false);
    const [mood, setMood] = useState<AssistantMood>("idle");
    const [bubble, setBubble] = useState<Bubble | null>(null);
    const [inputOpen, setInputOpen] = useState(false);

    const bubbleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const lastText = useRef<string | undefined>(undefined);
    const pick = (arr: string[]) => arr[Math.floor(Math.random() * arr.length)];

    // ── Show a bubble (the core method everything funnels through) ────────
    const say = useCallback((text: string, m: AssistantMood = "talking", navTo?: string) => {
        lastText.current = text;
        setBubble({ text, navTo });
        setMood(m);
        if (bubbleTimer.current) clearTimeout(bubbleTimer.current);
        bubbleTimer.current = setTimeout(() => {
            setBubble(null);
            setMood("idle");
        }, BUBBLE_MS);
    }, []);

    // ── notify() — the seam. Same as say(), but semantically a "nudge" and
    //    defaults to the notify mood (waving cat, etc). ────────────────────
    const notify = useCallback((message: string, m: AssistantMood = "notify") => {
        say(message, m);
    }, [say]);

    // ── Expose globally so any page can do window.assistant?.notify(...) ──
    useEffect(() => {
        (window as any).assistant = { notify };
        return () => { delete (window as any).assistant; };
    }, [notify]);

    // ── Greet ONCE, shortly after Cia appears ────────────────────────────
    useEffect(() => {
        if (dismissed) return;
        const t = setTimeout(() => {
            // only greet if she hasn't already said something
            if (!bubble) say(pick(GREETINGS), "happy");
        }, 1500);
        return () => clearTimeout(t);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);  // empty deps → runs once on mount

    // ── Idle poke: after inactivity with no bubble showing, drop a gentle
    //    nudge. (This REPLACES the old "sleep" effect — they shared the same
    //    timer and would race each other, so we keep only the friendlier one.)
    useEffect(() => {
        if (dismissed || bubble) return;  // don't poke while a bubble is up
        const t = setTimeout(() => {
            say(pick(IDLE_POKES), "notify");
        }, IDLE_MS);
        return () => clearTimeout(t);
    }, [bubble, dismissed, say]);

    const dismiss = useCallback(() => {
        setDismissed(true);
        if (bubbleTimer.current) clearTimeout(bubbleTimer.current);
    }, []);

    return {
        dismissed, mood, bubble, inputOpen,
        setInputOpen, say, notify, dismiss,
        getLastText: () => lastText.current,
        wake: () => setMood((m) => (m === "sleeping" ? "idle" : m)),
    };
}