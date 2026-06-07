/**
 * matchInput.ts — the only "thinking" Cia does.
 * ════════════════════════════════════════════════════════════════════════
 *
 * A pure function: user text in, a structured AssistantReply out. No state, no I/O,
 * no dependencies beyond the knowledge file — so it's trivially testable and
 * runs instantly in the browser.
 *
 * Strategy (cheap and predictable, no LLM):
 *   1. Normalize the input (lowercase, strip punctuation).
 *   2. Try NAVIGATION first — if they're asking "where is X", that's the most
 *      useful answer, so it wins over chatter.
 *   3. Try CHATTER — greetings, compliments, etc.
 *   4. Fall back to a gentle nudge.
 *
 * Matching is keyword containment with a light score (longer trigger phrases
 * that match are stronger signals than single short words). This is enough for
 * a finite, known app surface — we don't need fuzzy edit-distance here.
 */

import { CHATTER, FALLBACK_REPLIES, NAV_MAP, type AssistantMood } from "./assistant-knowledge";

export interface AssistantReply {
  type: "nav" | "chatter" | "fallback";
  text: string;
  mood: AssistantMood;
  /** Present only for nav results that have a destination. */
  navTo?: string;
}

/** Lowercase, strip punctuation, collapse whitespace. */
function normalize(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Pick a random element, avoiding `last` so replies don't repeat back-to-back. */
function pickRandom(arr: string[], last?: string): string {
  if (arr.length === 1) return arr[0];
  const pool = last ? arr.filter((x) => x !== last) : arr;
  return pool[Math.floor(Math.random() * pool.length)];
}

/**
 * Score how well a normalized input matches a list of triggers.
 * A trigger "hits" if it appears as a substring (word-ish) of the input, or
 * the input appears in the trigger (handles "niche" vs "my niche"). Longer
 * matched triggers score higher — "brand deals" is a stronger signal than "i".
 */
function scoreTriggers(input: string, triggers: string[]): number {
  let best = 0;
  const padded = ` ${input} `;
  for (const t of triggers) {
    const trigger = t.toLowerCase();
    if (padded.includes(` ${trigger} `) || input.includes(trigger)) {
      best = Math.max(best, trigger.length);
    }
  }
  return best;
}

/**
 * Match user input to a reply. `lastText` lets the caller pass Cia's previous
 * line so the random pickers avoid immediate repeats.
 */
export function matchInput(rawInput: string, lastText?: string): AssistantReply {
  const input = normalize(rawInput);

  if (!input) {
    return { type: "fallback", text: pickRandom(FALLBACK_REPLIES, lastText), mood: "idle" };
  }

  // ── 1. Navigation (wins — "where is X" is the most useful answer) ──────
  let bestNav: { score: number; entry: (typeof NAV_MAP)[number] } | null = null;
  for (const entry of NAV_MAP) {
    const score = scoreTriggers(input, entry.triggers);
    if (score > 0 && (!bestNav || score > bestNav.score)) {
      bestNav = { score, entry };
    }
  }

  // ── 2. Chatter ─────────────────────────────────────────────────────────
  let bestChat: { score: number; key: string } | null = null;
  for (const [key, intent] of Object.entries(CHATTER)) {
    const score = scoreTriggers(input, intent.triggers);
    if (score > 0 && (!bestChat || score > bestChat.score)) {
      bestChat = { score, key };
    }
  }

  // Prefer whichever matched more strongly; on a tie, navigation wins (more useful).
  const navScore = bestNav?.score ?? 0;
  const chatScore = bestChat?.score ?? 0;

  if (navScore > 0 && navScore >= chatScore) {
    return {
      type: "nav",
      text: bestNav!.entry.answer,
      mood: "talking",
      navTo: bestNav!.entry.navTo,
    };
  }

  if (chatScore > 0) {
    const intent = CHATTER[bestChat!.key];
    return {
      type: "chatter",
      text: pickRandom(intent.replies, lastText),
      mood: intent.mood,
    };
  }

  // ── 3. Fallback ──────────────────────────────────────────────────────────
  return { type: "fallback", text: pickRandom(FALLBACK_REPLIES, lastText), mood: "idle" };
}
