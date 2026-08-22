"use client";

import Link from "next/link";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  type LucideIcon,
  ArrowRight,
  Sparkles,
  Brain,
  PenTool,
  ChessQueen,
  Flame,
  Fingerprint,
  Layers,
  UserStar,
  Lightbulb,
  ChevronDown,
  CircleDollarSign
} from "lucide-react";
import {
  XCard,
  LinkedInCard,
  InstagramCard,
  YouTubeCard,
  YouTubeShortsCard,
  QuizCard,
} from "@/components/SocialMediaCards";
import Footer from "@/components/Footer";

// Modern sans for headings — overrides the global serif display, keeps the
// page editorial and clean. (DM Sans is already loaded → no extra bundle cost.)
const SANS = "[font-family:var(--font-dm-sans)]";

// ─── Hero ───────────────────────────────────────────────────────

function HeroBackground() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      {/* Fine technical grid, faded out toward the edges */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--color-border)_1px,transparent_1px),linear-gradient(to_bottom,var(--color-border)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_55%_55%_at_50%_40%,black,transparent_80%)] [background-size:46px_46px] opacity-50" />

      {/* Soft breathing glows — scale/opacity only, no drifting (stays calm) */}
      <motion.div
        className="absolute -top-24 left-1/2 h-[26rem] w-[26rem] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(199,93,58,0.16),transparent_65%)] blur-3xl"
        animate={{ scale: [1, 1.12, 1], opacity: [0.55, 0.85, 0.55] }}
        transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-[-4rem] bottom-[-6rem] h-[22rem] w-[22rem] rounded-full bg-[radial-gradient(circle,rgba(212,160,76,0.14),transparent_70%)] blur-3xl"
        animate={{ scale: [1.05, 0.95, 1.05], opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 13, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Hairline sheen at the very top */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--color-primary)]/30 to-transparent" />
    </div>
  );
}

function Hero() {
  return (
    <header className="relative isolate overflow-hidden bg-[var(--color-background)]">
      <HeroBackground />
      <div className="mx-auto max-w-5xl px-6 pt-24 pb-16 text-center md:pt-32 md:pb-24">
        <motion.span
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className={`${SANS} relative inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-white/60 px-4 py-1.5 text-xs font-medium tracking-wide text-[var(--color-muted)] backdrop-blur`}
        >
          {/* Micro-shimmer: a soft pulsing ring on the border */}
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 animate-pulse rounded-full ring-1 ring-[var(--color-primary)]/25"
          />
          <Sparkles className="relative h-3.5 w-3.5 text-[var(--color-primary)]" />
          <span className="relative">A swarm of AI agents for creators</span>
        </motion.span>

        <div className="relative mt-7">
          {/* Breathing ambient aura behind the core typography */}
          <motion.span
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-1/2 h-[300px] w-[500px] max-w-full -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#FFEBE5] opacity-40 blur-[90px] filter"
            animate={{ scale: [1, 1.12, 1] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className={`${SANS} relative mx-auto max-w-4xl text-[clamp(2.6rem,7vw,5rem)] leading-[0.98] font-semibold tracking-[-0.03em] text-balance text-[var(--color-text)]`}
          >
            Cupid

          </motion.h1>
          <p className="font-xl">A complete AI agents suite for content creation & influencers</p>
        </div>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
          className="mx-auto mt-6 max-w-xl text-[15px] leading-relaxed text-pretty text-[var(--color-muted)] md:text-base"
        >
          Cupid learns your voice, tracks what&apos;s trending in your niche, and ships
          platform-native posts on your schedule — so you create more and grind less.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="mt-9 flex flex-wrap items-center justify-center gap-3"
        >
          <Link
            href="/signin"
            className={`${SANS} group inline-flex items-center gap-2 rounded-full bg-[var(--color-primary)] px-6 py-3 text-sm font-medium text-white shadow-[0_10px_30px_-10px_rgba(199,93,58,0.6)] transition-all duration-300 hover:scale-[1.02] hover:shadow-[0_0_25px_rgba(239,68,68,0.15)]`}
          >
            Start for free
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            href="#showcase"
            className={`${SANS} inline-flex items-center rounded-full border border-[var(--color-border)] bg-white/50 px-6 py-3 text-sm font-medium text-[var(--color-text)] backdrop-blur transition-colors hover:border-[var(--color-border-hover)]`}
          >
            See results
          </Link>
        </motion.div>
      </div>
    </header>
  );
}

// ─── Interactive Agent Swarm ────────────────────────────────────

type Agent = { label: string; builds: string; icon: LucideIcon; tint: string };

const AGENTS: Agent[] = [
  {
    label: "Content Creator",
    builds: "Drafts platform-native posts, end to end.",
    icon: PenTool,
    tint: "#C75D3A",
  },
  {
    label: "Influencer Agent",
    builds: "Tunes tone & persona to your audience.",
    icon: ChessQueen,
    tint: "#af6d58",
  },
  {
    label: "Personalization Agent",
    builds: "Adhere your style and tone",
    icon: UserStar,
    tint: "#3160c4",
  },
  {
    label: "Trends Researcher",
    builds: "Surfaces what's rising in your niche.",
    icon: Flame,
    tint: "#ce2921",
  },
  {
    label: "Earning Opportunity",
    builds: "Personal monitization coach, personalized earning plan",
    icon: CircleDollarSign,
    tint: "#e7a10b",
  },
];

function AgentSwarm() {
  const [hovered, setHovered] = useState<number | null>(null);
  const R = 38; // orbit radius (% of container)
  const nodes = AGENTS.map((a, i) => {
    const ang = (-90 + i * (360 / AGENTS.length)) * (Math.PI / 180);
    return { ...a, x: 50 + R * Math.cos(ang), y: 50 + R * Math.sin(ang) };
  });

  return (
    <section id="agents" className="border-t border-[var(--color-border)]">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2 lg:gap-20 lg:py-32">
        {/* Copy */}
        <div className="order-2 lg:order-1">
          <p
            className={`${SANS} mb-4 text-xs font-semibold tracking-[0.16em] text-[var(--color-primary)] uppercase`}
          >
            The architecture
          </p>
          <h2
            className={`${SANS} max-w-md text-[clamp(1.9rem,3.4vw,2.6rem)] leading-[1.05] font-semibold tracking-[-0.02em] text-[var(--color-text)]`}
          >
            A team of specialist agents, orbiting one core.
          </h2>
          <p className="mt-5 max-w-md text-[15px] leading-relaxed text-[var(--color-muted)]">
            Each agent owns one craft and reports to the Core AI. Hover any node to see exactly what
            it builds — they work in concert so every post is researched, written, and shaped to
            sound like you.
          </p>
          <ul className="mt-7 flex flex-wrap gap-2">
            {AGENTS.map((a, i) => (
              <li key={a.label}>
                <button
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  className={`${SANS} rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    hovered === i
                      ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                      : "border-[var(--color-border)] text-[var(--color-muted)] hover:border-[var(--color-border-hover)]"
                  }`}
                >
                  {a.label}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Swarm graphic */}
        <div className="order-1 mx-auto w-full max-w-md lg:order-2">
          <div className="relative aspect-square w-full">
            {/* Orbit rings */}
            <div
              aria-hidden
              className="absolute inset-[8%] rounded-full border border-dashed border-[var(--color-border)]"
            />
            <div
              aria-hidden
              className="absolute inset-[2%] rounded-full border border-[var(--color-border)]/50"
            />

            {/* Connection lines */}
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              className="absolute inset-0 h-full w-full"
            >
              {nodes.map((n, i) => (
                <line
                  key={n.label}
                  x1="50"
                  y1="50"
                  x2={n.x}
                  y2={n.y}
                  stroke={hovered === i ? n.tint : "var(--color-border)"}
                  strokeWidth={hovered === i ? 0.8 : 0.5}
                  strokeDasharray="2 2"
                  vectorEffect="non-scaling-stroke"
                  className="transition-all duration-300"
                />
              ))}
            </svg>

            {/* Core node */}
            <motion.div
              animate={{ scale: [1, 1.06, 1] }}
              transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
              className="absolute top-1/2 left-1/2 grid h-[22%] w-[22%] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-secondary)] text-white shadow-[0_0_0_8px_rgba(199,93,58,0.12),0_18px_40px_-12px_rgba(199,93,58,0.5)]"
            >
              <Brain className="h-1/2 w-1/2" strokeWidth={1.6} />
            </motion.div>

            {/* Sub-agent nodes */}
            {nodes.map((n, i) => {
              const Icon = n.icon;
              const active = hovered === i;
              return (
                <div
                  key={n.label}
                  className="absolute -translate-x-1/2 -translate-y-1/2"
                  style={{ left: `${n.x}%`, top: `${n.y}%` }}
                >
                  <motion.button
                    onMouseEnter={() => setHovered(i)}
                    onMouseLeave={() => setHovered(null)}
                    onFocus={() => setHovered(i)}
                    onBlur={() => setHovered(null)}
                    animate={{ y: [0, -6, 0] }}
                    transition={{ duration: 3.6 + i * 0.5, repeat: Infinity, ease: "easeInOut" }}
                    whileHover={{ scale: 1.14 }}
                    aria-label={`${n.label}: ${n.builds}`}
                    className="grid h-12 w-12 place-items-center rounded-full border bg-white shadow-sm transition-shadow outline-none md:h-14 md:w-14"
                    style={{
                      borderColor: active ? n.tint : "var(--color-border)",
                      boxShadow: active ? `0 10px 26px -10px ${n.tint}aa` : undefined,
                      color: n.tint,
                    }}
                  >
                    <Icon className="h-5 w-5" strokeWidth={1.7} />
                  </motion.button>

                  {/* Tooltip */}
                  <AnimatePresence>
                    {active && (
                      <motion.div
                        initial={{ opacity: 0, y: 6, scale: 0.96 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 6, scale: 0.96 }}
                        transition={{ duration: 0.18 }}
                        className="absolute top-full left-1/2 z-20 mt-2 w-44 -translate-x-1/2 rounded-4xl border border-[var(--color-border)] bg-white/95 p-3 text-center shadow-lg backdrop-blur"
                      >
                        <p className={`${SANS} text-xs font-semibold text-[var(--color-text)]`}>
                          {n.label}
                        </p>
                        <p className="mt-0.5 text-[11px] leading-snug text-[var(--color-muted)]">
                          {n.builds}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Features Suite (3 pillars) ─────────────────────────────────

const FEATURES = [
  {
    icon: Fingerprint,
    title: "Voice Authenticity Engine",
    body: "A private persona model learns your rhythm, vocabulary, and the words you'd never use — then checks every draft for fidelity before it ships.",
    tint: "#C75D3A",
  },
  {
    icon: Layers,
    title: "Multi-Platform Adaptation",
    body: "One idea, formatted natively for X, LinkedIn, Instagram, and YouTube — each with the right length, tone, and hooks for that audience.",
    tint: "#5A7A3E",
  },
  {
    icon: Lightbulb,
    title: "Automated Ideation",
    body: "Trend scouts watch your niche around the clock and surface fresh, on-brand angles, so you're never staring at a blank canvas.",
    tint: "#D4A04C",
  },
];

function Features() {
  return (
    <section id="features" className="border-t border-[var(--color-border)]">
      <div className="mx-auto max-w-6xl px-6 py-24 lg:py-32">
        <div className="mx-auto max-w-2xl text-center">
          <p
            className={`${SANS} mb-4 text-xs font-semibold tracking-[0.16em] text-[var(--color-primary)] uppercase`}
          >
            Built for creators
          </p>
          <h2
            className={`${SANS} text-[clamp(1.9rem,3.4vw,2.6rem)] leading-[1.05] font-semibold tracking-[-0.02em] text-[var(--color-text)]`}
          >
            Three engines doing the heavy lifting.
          </h2>
        </div>

        <div className="mt-16 grid gap-6 md:grid-cols-3">
          {FEATURES.map((f) => (
            <article
              key={f.title}
              className="group rounded-3xl border border-[var(--color-border)] bg-white/60 p-8 backdrop-blur transition-all duration-300 hover:-translate-y-1 hover:border-[var(--color-border-hover)] hover:shadow-lg"
            >
              <span
                className="grid h-12 w-12 place-items-center rounded-2xl transition-transform duration-300 group-hover:scale-105"
                style={{ backgroundColor: `${f.tint}1a`, color: f.tint }}
              >
                <f.icon className="h-6 w-6" strokeWidth={1.7} />
              </span>
              <h3
                className={`${SANS} mt-6 text-lg font-semibold tracking-[-0.01em] text-[var(--color-text)]`}
              >
                {f.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">{f.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── FAQ ────────────────────────────────────────────────────────

const FAQS = [
  {
    q: "What exactly do Cupid's AI agents do?",
    a: "A swarm of specialist agents research your niche, adapt findings to your persona, draft platform-native posts, and schedule them — an end-to-end pipeline from idea to publish, all tuned to your voice.",
  },
  {
    q: "Is it safe to let AI replicate my creator voice?",
    a: "Your persona model is private to your account and never used to train shared models. It only shapes your own drafts, and every output runs a fidelity check — if it doesn't sound like you, it's rewritten.",
  },
  {
    q: "Which platforms does Cupid support?",
    a: "X (Twitter), LinkedIn, Instagram, Facebook, and YouTube — each with native formatting, length, and tone. More platforms are added regularly.",
  },
  {
    q: "Will my content sound generic or actually like me?",
    a: "Cupid anchors to your writing samples first. Drafts inherit your sentence rhythm, vocabulary, and angles — not generic web filler — so they read as you, not as AI.",
  },
  {
    q: "Do I keep ownership of everything Cupid creates?",
    a: "Yes. You own every post you generate. Cupid only stores what's needed to operate the service and never sells your data.",
  },
];

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-[var(--color-border)]">
      <h3>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className={`${SANS} flex w-full items-center justify-between gap-4 py-6 text-left text-[15px] font-medium text-[var(--color-text)] md:text-base`}
        >
          {q}
          <ChevronDown
            className={`h-5 w-5 flex-shrink-0 text-[var(--color-primary)] transition-transform duration-300 ${open ? "rotate-180" : ""}`}
          />
        </button>
      </h3>
      {/* grid-rows trick: smooth height, zero layout shift */}
      <div
        className={`grid transition-all duration-300 ease-out ${open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}
      >
        <div className="overflow-hidden">
          <p className="pr-8 pb-6 text-sm leading-relaxed text-[var(--color-muted)]">{a}</p>
        </div>
      </div>
    </div>
  );
}

function Faq() {
  return (
    <section id="faq" className="border-t border-[var(--color-border)]">
      <div className="mx-auto max-w-3xl px-6 py-24 lg:py-32">
        <div className="text-center">
          <p
            className={`${SANS} mb-4 text-xs font-semibold tracking-[0.16em] text-[var(--color-primary)] uppercase`}
          >
            Questions
          </p>
          <h2
            className={`${SANS} text-[clamp(1.9rem,3.4vw,2.6rem)] leading-[1.05] font-semibold tracking-[-0.02em] text-[var(--color-text)]`}
          >
            Everything you&apos;re wondering.
          </h2>
        </div>
        <div className="mt-12">
          {FAQS.map((f) => (
            <FaqItem key={f.q} q={f.q} a={f.a} />
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Content Showcase (kept verbatim per request) ───────────────

function PostsPreview() {
  return (
    <section id="showcase" className="border-t border-border bg-muted/20">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <h2 className="mb-3 text-center text-[clamp(1.8rem,3vw,2.4rem)] tracking-tight">
          Posts that already sound like you
        </h2>
        <p className="mb-14 text-center">
          Intelligence personalized to each social media platform formats and tone
        </p>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <XCard
            name="Hubert"
            handle="hthieblot"
            content={"Just move to SF, it will change your life.\nGo in debt if you have to."}
            mediaUrl="/media/sf_scene.png"
          />
          <LinkedInCard
            name="AIM"
            content="Google India has signed a five-year lease for approximately 617,000 square feet of office space at Atrium Place in Gurugram, with a total rental outlay of Rs 671 crore, according to transaction documents accessed by Propstack. The space, spread across floors two to 16 of Tower 1, is part of a joint venture between DLF and Hines, and the lease commenced on 1 October 2025."
            mediaUrl="/media/Google_deal.jpg"
          />
          <InstagramCard
            name="Rakul Bansal"
            content="Just shipped persona fidelity scoring for Cupid."
            mediaUrl="/media/founder_journey.mp4"
          />
          <YouTubeShortsCard
            name="Adya Prasad"
            handle="adyaprasad"
            content="Just shipped persona fidelity scoring for Cupid AI."
            mediaUrl="/media/food_comedy.mp4"
          />
          <YouTubeCard
            name="Rakul Bansal"
            content="Just shipped persona fidelity scoring for Cupid."
            mediaUrl="/media/creative_designer.mp4"
          />
          <QuizCard
            name="Adya Prasad"
            handle="adyaprasad"
            question="Which framework should I use for Cupid's agent layer?"
            options={["LangGraph", "CrewAI", "AutoGen", "Build from scratch"]}
            timeLeft=""
          />
        </div>
      </div>
    </section>
  );
}

// ─── Page ───────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <main className="min-h-screen overflow-x-hidden bg-[var(--color-background)] text-[var(--color-text)] antialiased">
      <Hero />
      <AgentSwarm />
      <PostsPreview />
      <Features />
      <Faq />
      <Footer />
    </main>
  );
}
