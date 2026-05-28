/**
 * assistant-knowledge.ts — Cia's entire brain.
 * ════════════════════════════════════════════════════════════════════════
 *
 * Cia is a NAVIGATOR with personality, not a chatbot. This file is pure data:
 *
 *   1. NAV_MAP   — every page/setting/option in Cupid, with the phrases people
 *                  use to ask for it and the short answer Cia speaks.
 *   2. CHATTER   — wholesome canned replies, grouped by intent, picked at
 *                  random so Cia never feels repetitive.
 *
 * No logic lives here. matchInput.ts reads this to decide what Cia says.
 * Growing Cia = adding entries/lines here. The code never changes.
 *
 * ⚠️  ADJUST: the routes and labels below are drafted from the app we built.
 * Correct any nav label / href to match your real sidebar exactly.
 */

/* ────────────────────────────────────────────────────────────────────────
   Moods — the fixed set the UI maps to gif assets. Code references these
   names only; you swap/expand the actual gifs per mood freely.
   ──────────────────────────────────────────────────────────────────────── */

export type AssistantMood =
    | "idle"       // default hovering
    | "happy"      // greetings, compliments
    | "talking"    // delivering a navigation answer
    | "thinking"   // brief beat after input
    | "notify"     // has a nudge to show
    | "sleeping";  // after long inactivity

/* ────────────────────────────────────────────────────────────────────────
   Navigation map
   ──────────────────────────────────────────────────────────────────────── */

export interface NavEntry {
    id: string;
    /** What Cia says when matched. Keep it short and warm. */
    answer: string;
    /** Optional route for a "take me there" button. */
    navTo?: string;
    /** Phrases/keywords that should match this entry. Lowercase, no punctuation. */
    triggers: string[];
}
export const NAV_MAP: NavEntry[] = [
    {
        id: "create",
        answer: "The Create page is where you generate posts! ✨",
        navTo: "/create",
        triggers: [
            "create", "new post", "generate", "make a post", "write",
            "compose", "content", "make content", "start",
        ],
    },
    {
        id: "trends",
        answer: "Trends shows fresh news in your niche to spark ideas! 📈",
        navTo: "/trends",
        triggers: [
            "trends", "trending", "news", "what's hot", "ideas",
            "topics", "inspiration", "trend",
        ],
    },
    {
        id: "insights",
        answer: "Insights has your followers, views & top content! 📊",
        navTo: "/insights",
        triggers: [
            "insights", "stats", "analytics", "followers", "views",
            "subscribers", "performance", "metrics", "numbers", "growth",
        ],
    },
    {
        id: "history",
        answer: "History keeps every post you've made — tap to revisit! 🕘",
        navTo: "/history",
        triggers: [
            "history", "past posts", "old posts", "previous", "my posts",
            "what i made", "saved", "earlier",
        ],
    },
    {
        id: "earn",
        answer: "Earn maps your money paths & matched opportunities! 💰",
        navTo: "/earn",
        triggers: [
            "earn", "money", "income", "monetize", "monetise", "revenue",
            "brand deals", "affiliate", "opportunities", "sponsor",
            "make money", "earning",
        ],
    },
    {
        id: "profile",
        answer: "Your Profile holds your name, bio & creator details! 👤",
        navTo: "/profile",
        triggers: [
            "profile", "my profile", "account", "my info", "edit profile",
            "settings", "my details", "bio", "name",
        ],
    },
    {
        id: "niche",
        answer: "Change your niche in Profile → Content Niche! 🎯",
        navTo: "/profile",
        triggers: [
            "niche", "my niche", "change niche", "category", "content niche",
            "topic", "what i post about",
        ],
    },
    {
        id: "connections",
        answer: "Connect YouTube & socials in Connections! 🔗",
        navTo: "/connections",
        triggers: [
            "connect", "connections", "youtube", "link account", "social",
            "instagram", "integrations", "accounts", "platform", "oauth",
        ],
    },
    {
        id: "logout",
        answer: "You can log out from the menu — see you soon! 👋",
        triggers: ["logout", "log out", "sign out", "exit", "leave"],
    },
];

/* ────────────────────────────────────────────────────────────────────────
   Chatter bank — wholesome canned replies by intent.
   Each intent maps to an array; matchInput picks one at random (non-repeating).
   The mood drives which gif plays. Add as many lines as you like.
   ──────────────────────────────────────────────────────────────────────── */

export interface ChatterIntent {
    /** Phrases that trigger this intent. Lowercase, no punctuation. */
    triggers: string[];
    /** Cia's possible replies — one is chosen at random. */
    replies: string[];
    mood: AssistantMood;
}

export const CHATTER: Record<string, ChatterIntent> = {
    greeting: {
        triggers: ["hi", "hello", "hey", "yo", "hiya", "good morning", "good evening", "sup"],
        replies: ["meow! 🐾", "hi friend! 💕", "hello! happy to see you", "hey you! ✨", "purr~ hello!"],
        mood: "happy",
    },
    compliment: {
        triggers: ["cute", "adorable", "love you", "you're sweet", "good cat", "nice", "best", "lovely", "pretty"],
        replies: [
            "meow! 🐾",
            "thank you! 💕",
            "you just made my day!",
            "my whole family is cute 🐱",
            "you're cuter! ✨",
            "*happy purring*",
        ],
        mood: "happy",
    },
    thanks: {
        triggers: ["thanks", "thank you", "ty", "thx", "appreciate", "helpful"],
        replies: ["anytime! 🐾", "happy to help! 💕", "that's what i'm here for!", "meow of honor ✨"],
        mood: "happy",
    },
    howareyou: {
        triggers: ["how are you", "how r u", "you ok", "whats up", "what's up", "how you doing"],
        replies: ["cozy in my box! 📦", "purring along~ 🐾", "great, now that you're here! 💕", "living my best cat life!"],
        mood: "happy",
    },
    name: {
        triggers: ["your name", "who are you", "what are you", "whats your name", "what's your name"],
        replies: ["i'm Cia, your little helper! 🐱", "Cia! here to help you find things ✨", "Cia the cat, at your service! 🐾"],
        mood: "happy",
    },
    bye: {
        triggers: ["bye", "goodbye", "see you", "cya", "later", "good night"],
        replies: ["bye friend! 👋", "see you soon! 💕", "i'll be in my box 📦", "come back anytime! 🐾"],
        mood: "happy",
    },
    joke: {
        triggers: ["joke", "make me laugh", "funny", "bored", "entertain me"],
        replies: [
            "why don't cats play poker? too many cheetahs! 😹",
            "i'm feline good today! 🐾",
            "you've got to be kitten me right meow 😼",
            "i'd tell you a fish joke but it's a little fishy 🐟",
        ],
        mood: "happy",
    },
};

export const GREETINGS: string[] = [
    "hey, how's it going?",
    "I'm Cia, your assistant!",
    "what do you wanna create today?",
    "something on your mind? Cia is here",
    "welcome to Cupid, me Cia...",
];
 

export const FALLBACK_REPLIES: string[] = [
    "hmm, not sure try the menu?",
    "didn't understood! ask me where something is...",
    "meow! maybe check the sidebar",
    "oops something wrong, retry" ,
];

/* ────────────────────────────────────────────────────────────────────────
   Idle pokes — Cia says these unprompted after inactivity (optional charm).
   ──────────────────────────────────────────────────────────────────────── */

export const IDLE_POKES: string[] = [
    "psst… need anything? 🐾",
    "i'm here if you need me! 💕",
    "*stretches* ready when you are ✨",
    "still here, just chilling 🐱",
    "forgot something? just ask!",
    "hey, i need some milk...",
    "actually i'm bored......"

];