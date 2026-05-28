# Cia (Assistant) — Integration Guide

A frontend-only screen buddy named **Cia**. The files are named `assistant-*`
(the folder/feature is "assistant"); her on-screen *name* stays "Cia". No
backend, no storage, no new dependencies.

---

## File placement

```
frontend/<your-choice>/assistant/
├── assistant-knowledge.ts   ← brain: nav map + chatter bank
├── matchInput.ts            ← pure matching logic (tested)
├── useAssistant.ts          ← session state + notify() seam
├── AssistantBubble.tsx      ← speech bubble + tiny input
└── Assistant.tsx            ← the cat (drag, close, moods)

frontend/public/assistant/
├── idle.gif                 ← drop your mochi gifs here, one per mood
├── happy.gif
├── talking.gif
├── thinking.gif
├── notify.gif
└── sleeping.gif
```

> Asset path note: `Assistant.tsx` loads gifs from `/assistant/<mood>.gif`
> (i.e. `frontend/public/assistant/`). If you'd rather keep them in
> `public/cia/`, change the one `ASSET` line near the top of `Assistant.tsx`.

---

## Step 1 — Add the gif assets (placeholder mochi for now)

Put one gif per mood in `frontend/public/assistant/`, named exactly
`<mood>.gif`. For now copy your mochi cat to all six names — the code references
*moods*, so distinct animations later are a pure file swap. Missing files
auto-fall back to `idle.gif`.

Moods: `idle`, `happy`, `talking`, `thinking`, `notify`, `sleeping`.

---

## Step 2 — Mount once

In your dashboard layout (wrapping all logged-in pages):

```tsx
import Assistant from "@/components/assistant/Assistant";  // adjust path to your choice

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    return (
        <>
            {children}
            <Assistant />
        </>
    );
}
```

Cia now hovers bottom-right on every dashboard page — draggable, closeable, with
the click-to-ask input.

---

## Step 3 — (Optional) Fire notifications from events you already have

Cia exposes a global so any page can make her pop a bubble — note the global is
now **`window.assistant`** (renamed along with everything else):

```tsx
// when a run completes, on the Create page:
(window as any).assistant?.notify("your post is ready! 🎉", "happy");

// after loading trends:
(window as any).assistant?.notify(`${count} fresh trends for you! 📈`, "notify");
```

No backend needed — these are frontend events you already detect.

---

## How Cia decides what to say

`matchInput(text)` runs in the browser:
1. **Navigation first** — `NAV_MAP` triggers → "Change your niche in Profile →
   Content Niche!" + a *take me there* button. Navigation wins ties (most useful).
2. **Chatter** — greetings/compliments/thanks/jokes, random non-repeating reply.
3. **Fallback** — a gentle nudge, never a dead end.

Input is capped at 10 words (enforced in `AssistantBubble`).

---

## Growing Cia (all data, no code)

- **Add a destination:** push to `NAV_MAP` in `assistant-knowledge.ts`
  (`answer`, optional `navTo`, `triggers`).
- **Add personality:** add lines to a `CHATTER` intent's `replies`, or a new intent.
- **Add a mood:** extend the `AssistantMood` type, drop `<mood>.gif` in
  `public/assistant/`, reference it from a chatter intent or `notify` call.

⚠️ **Adjust the routes** in `NAV_MAP` to match your real sidebar
(`/create`, `/trends`, `/insights`, `/history`, `/earn`, `/profile`, `/connections`).

---

## What the rename touched (for your reference)

If you ever cross-check: `cia-knowledge.ts → assistant-knowledge.ts`,
`useCia → useAssistant`, `CiaBubble → AssistantBubble`, `Cia.tsx → Assistant.tsx`
(default export `Assistant`), type `CiaMood → AssistantMood`,
`CiaReply → AssistantReply`, and the global `window.cia → window.assistant`. The
cat's *name* "Cia" is intentionally kept in the chatter replies and comments —
that's her identity, independent of the filenames.

---

## The future-backend seam

When you want notifications pushed while the user *isn't* on the triggering page,
add a ~20-line poller that fetches nudges and calls the same
`window.assistant.notify(...)`. Cia doesn't change — backend notifications are
purely additive. That's why `notify()` is a single method.

---

## Quick test checklist

1. Mount `<Assistant />`, add gifs to `public/assistant/`, `npm run dev`.
2. Cia appears bottom-right; drag her — she follows and stays on screen.
3. Click → input opens. "where do I earn money" → points to Earn + working button.
4. "hi" / "you're cute" → wholesome random reply; repeat to see variety.
5. Gibberish → gentle fallback.
6. Hover → close (×); click → gone for the session (returns on reload).
7. Console: `window.assistant.notify("test! 🎉","happy")` → bubble pops.
```