import Link from "next/link";
import { XCard, LinkedInCard, InstagramCard, FacebookCard, YouTubeCard, YouTubeShortsCard, PollCard } from "@/components/SocialMediaCards";

const AGENTS = [
  { n: "01", name: "Persona Agent", desc: "Learns your voice from writing samples. Builds a living model of your tone, vocabulary, and domain depth." },
  { n: "02", name: "Research Agent", desc: "Finds angles, sources, and ideas tailored to your expertise. Runs autonomously or on-demand." },
  { n: "03", name: "Trend Agent", desc: "Monitors Reddit, HackerNews, and RSS in your domain. Surfaces what is rising before it peaks." },
  { n: "04", name: "Composer Agent", desc: "Assembles platform-specific posts. Runs a fidelity check — if it doesn't sound like you, it regenerates." },
];

const TRAITS = [
  { label: "Sounds exactly like you", sub: "Not AI. Not a template." },
  { label: "Platform-native formatting", sub: "LinkedIn, X, Threads, Reddit." },
  { label: "Trend-to-post in minutes", sub: "Signal to publish, automated." },
  { label: "Your data stays private", sub: "Persona stored only for you." },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-background overflow-x-hidden">

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 pt-24 pb-20 grid lg:grid-cols-2 gap-16 items-center">
        <div className="space-y-7 animate-float-up">
          <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-primary">
            For creators & influencers
          </p>
          <h1
            className="text-[clamp(2.5rem,5vw,3.8rem)] font-normal leading-[1.08] tracking-tight text-foreground"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Post like yourself,<br />
            <em className="text-primary">not like everyone else.</em>
          </h1>
          <p className="text-base text-muted-foreground leading-relaxed max-w-md">
            Cupid Agents get trained on your voice, tracks what's trending in your niche, and writes posts that sound authentically like you — across every platform, on your schedule.
          </p>
          <div className="flex gap-3 flex-wrap">
            <Link href="/register" className="btn-primary">
              Start for free
            </Link>
            <Link href="#agents" className="btn-secondary">
              See how it works
            </Link>
          </div>
        </div>

        {/* Floating social card preview */}
        <div className="relative h-[420px] hidden lg:block animate-fade-in">
          <div className="absolute top-4 right-2 rotate-2 z-10 drop-shadow-xl">
            <LinkedInCardImg />
          </div>
          <div className="absolute bottom-4 left-2 -rotate-1 z-20 drop-shadow-xl">
            <XCardImg />
          </div>
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6"><div className="h-px bg-border" /></div>

      {/* ── Agents ───────────────────────────────────────────── */}
      <section id="agents" className="max-w-6xl mx-auto px-6 py-24 grid lg:grid-cols-2 gap-16 items-center">
        <div className="flex justify-center order-2 lg:order-1">
          <AgentOrbit />
        </div>
        <div className="order-1 lg:order-2">
          <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-primary mb-3">The pipeline</p>
          <h2
            className="text-[clamp(1.8rem,3vw,2.4rem)] font-normal tracking-tight text-foreground mb-8"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Four agents.<br />One authentic voice.
          </h2>
          <div className="border border-border rounded-xl overflow-hidden divide-y divide-border">
            {AGENTS.map((a) => (
              <div key={a.n} className="flex gap-4 p-4 bg-card hover:bg-muted/30 transition-colors">
                <span className="text-[10px] font-bold tracking-widest text-primary mt-0.5 w-5 shrink-0">{a.n}</span>
                <div>
                  <p className="text-sm font-medium text-foreground mb-0.5" style={{ fontFamily: "var(--font-display)" }}>{a.name}</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">{a.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="agents" className="max-w-6xl mx-auto px-6 py-15 items-center ">
        <h2 >For content creation lover and dedicated influencers!</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <XCard
            name="Adya Prasad"
            handle="adyaprasad"
            content="Just shipped persona fidelity scoring for Cupid."
            time="2h"
          />
          <FacebookCard
            name="Rakul Bansal"
            content="Just shipped persona fidelity scoring for Cupid."
          />
          <LinkedInCard
            name="Rakul Bansal"
            content="Just shipped persona fidelity scoring for Cupid."
          />
          <InstagramCard
            name="Rakul Bansal"
            content="Just shipped persona fidelity scoring for Cupid." />

          {/* No media — gradient placeholder */}
          <YouTubeShortsCard
            name="Adya Prasad"
            handle="adyaprasad"
            content="Just shipped persona fidelity scoring for Cupid AI. Cosine similarity hits different."
          />

          {/* With thumbnail */}
          <YouTubeShortsCard
            name="Adya Prasad"
            handle="adyaprasad"
            content="Just shipped persona fidelity scoring for Cupid AI."
            mediaUrl="/short-thumbnail.jpg"
          />

          <YouTubeCard name="Rakul Bansal"
            content="Just shipped persona fidelity scoring for Cupid." />

          <PollCard
            name="Adya Prasad"
            handle="adyaprasad"
            question="Which framework should I use for Cupid's agent layer?"
            options={["LangGraph", "CrewAI", "AutoGen", "Build from scratch"]}
            timeLeft="18h left"
          />

          {/* Voted state — shows filled bars with winner highlighted */}
          <PollCard
            name="Adya Prasad"
            handle="adyaprasad"
            question="Which framework should I use for Cupid's agent layer?"
            options={["LangGraph", "CrewAI", "AutoGen", "Build from scratch"]}
            votes={[48, 27, 16, 9]}
            totalVotes={1284}
            timeLeft="18h left"
          />

        </div>
      </section>

      {/* ── Traits ───────────────────────────────────────────── */}
      <section className="border-y border-border bg-muted/20 py-14">
        <div className="max-w-6xl mx-auto px-6 grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {TRAITS.map((t) => (
            <div key={t.label}>
              <div className="w-6 h-0.5 bg-primary rounded mb-3" />
              <p className="text-sm font-medium text-foreground mb-1" style={{ fontFamily: "var(--font-display)" }}>{t.label}</p>
              <p className="text-xs text-muted-foreground">{t.sub}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────── */}
      <section className="max-w-2xl mx-auto px-6 py-28 text-center">
        <h2
          className="text-[clamp(2rem,4vw,2.8rem)] font-normal tracking-tight text-foreground mb-4"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Your audience is already<br />
          <em className="text-primary">paying attention.</em>
        </h2>
        <p className="text-sm text-muted-foreground mb-8">Set up your persona once. Let Cupid handle the rest.</p>
        <Link href="/register" className="px-8 py-3 rounded-lg bg-foreground text-background text-sm font-medium hover:opacity-80 transition-opacity inline-block">
          Create your persona
        </Link>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="border-t border-border py-6">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between">
          <span className="text-primary italic text-lg" style={{ fontFamily: "var(--font-display)" }}>cupid</span>
          <span className="text-xs text-muted-foreground">Open source · MIT license</span>
        </div>
      </footer>

    </main>
  );
}

/* ─── LinkedIn Card ──────────────────────────────────────────── */
function LinkedInCardImg() {
  return (
    <div className="w-72 bg-white rounded-2xl border border-gray-200 p-4">
      <div className="flex gap-2.5 mb-3">
        <div className="w-9 h-9 rounded-full bg-blue-700 text-white text-[11px] font-bold flex items-center justify-center shrink-0">AP</div>
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] font-semibold text-gray-900 leading-none">Adya Prasad</span>
            <span className="text-[9px] text-blue-700 border border-blue-700 px-1 rounded leading-tight">1st</span>
          </div>
          <p className="text-[10px] text-gray-500 mt-0.5">AI/ML Engineer · Open-source tools</p>
          <p className="text-[10px] text-gray-400 mt-0.5">4h · 🌐</p>
        </div>
      </div>
      <p className="text-[12px] text-gray-800 leading-relaxed mb-3">
        Most engineers treat RAG as a retrieval problem.<br />
        It's actually a <strong>trust problem.</strong><br /><br />
        Your model can retrieve perfectly and still hallucinate if it doesn't know when to say — I don't know.
      </p>
      <div className="border-t border-gray-100 pt-2.5">
        <div className="flex justify-between text-[10px] text-gray-400 mb-2.5">
          <span>👍 ❤️ 41 reactions</span>
          <span>12 comments · 5 reposts</span>
        </div>
        <div className="flex justify-around text-[10px] text-gray-500 font-medium border-t border-gray-100 pt-2">
          {["👍 Like", "💬 Comment", "🔁 Repost", "✉️ Send"].map((a) => (
            <span key={a} className="cursor-pointer hover:text-blue-600 transition-colors">{a}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── X Card ─────────────────────────────────────────────────── */
function XCardImg() {
  return (
    <div className="w-72 bg-white rounded-2xl border border-gray-200 p-4">
      <div className="flex gap-2.5">
        <div className="w-9 h-9 rounded-full bg-[#d47a03] text-white text-[11px] font-bold flex items-center justify-center shrink-0">AP</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 mb-1 flex-wrap">
            <span className="text-[12px] font-bold text-gray-900">Adya Prasad</span>
            <svg className="w-3.5 h-3.5 text-blue-500 shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M22.25 12c0-1.43-.88-2.67-2.19-3.34.46-1.39.2-2.9-.81-3.91s-2.52-1.27-3.91-.81c-.66-1.31-1.91-2.19-3.34-2.19s-2.67.88-3.33 2.19c-1.4-.46-2.91-.2-3.92.81s-1.26 2.52-.8 3.91C2.88 9.33 2 10.57 2 12s.88 2.67 2.19 3.34c-.46 1.39-.2 2.9.81 3.91s2.52 1.27 3.91.81c.66 1.31 1.91 2.19 3.34 2.19s2.67-.88 3.33-2.19c1.4.46 2.91.2 3.92-.81s1.26-2.52.8-3.91C21.36 14.67 22.25 13.43 22.25 12zm-13.47 4L5.5 11.79l1.41-1.41 1.87 1.86 4.72-4.72 1.41 1.41L8.78 16z" />
            </svg>
            <span className="text-[10px] text-gray-400">@adyaprasad · 2h</span>
          </div>
          <p className="text-[12px] text-gray-900 leading-relaxed mb-3">
            The best technical content doesn't explain what a thing is.<br /><br />
            It explains <strong>why you were wrong about what it is.</strong>
          </p>
          <div className="flex gap-4 text-[10px] text-gray-400">
            <span>💬 2.1K</span>
            <span>🔁 4.8K</span>
            <span>❤️ 18.4K</span>
            <span>📊 3.2M</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Agent Orbit SVG ────────────────────────────────────────── */
function AgentOrbit() {
  const agents = [
    { label: "Persona", angle: 270, color: "#d47a03" },
    { label: "Research", angle: 0, color: "#2a3852" },
    { label: "Trend", angle: 90, color: "#d47a03" },
    { label: "Composer", angle: 180, color: "#2a3852" },
  ];
  const cx = 190, cy = 190, r = 110;

  return (
    <svg width="340" height="340" viewBox="0 0 380 380" fill="none" className="max-w-full h-auto">
      <circle cx={cx} cy={cy} r={r} stroke="#e8ddd0" strokeWidth="1" strokeDasharray="4 6" />
      <circle cx={cx} cy={cy} r={r + 28} stroke="#d47a03" strokeWidth="0.5" strokeOpacity="0.2" />
      <circle cx={cx} cy={cy} r={28} fill="#fff6ed" stroke="#d47a03" strokeWidth="1" />
      <circle cx={cx} cy={cy} r={20} fill="#d47a03" fillOpacity="0.08" />
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize="9" fontFamily="DM Sans,system-ui" fontWeight="500" letterSpacing="0.08em" fill="#d47a03">
        CUPID
      </text>
      {agents.map((agent) => {
        const rad = (agent.angle * Math.PI) / 180;
        const nx = cx + r * Math.cos(rad);
        const ny = cy + r * Math.sin(rad);
        const lx = cx + (r + 46) * Math.cos(rad);
        const ly = cy + (r + 46) * Math.sin(rad);
        return (
          <g key={agent.label}>
            <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={agent.color} strokeWidth="0.75" strokeOpacity="0.25" strokeDasharray="3 4" />
            <circle cx={nx} cy={ny} r={18} fill={agent.color} fillOpacity="0.06"
              style={{ animation: "pulse-ring 3s ease-in-out infinite", animationDelay: `${agents.indexOf(agent) * 0.6}s`, transformOrigin: `${nx}px ${ny}px` }}
            />
            <circle cx={nx} cy={ny} r={11} fill={agent.color === "#d47a03" ? "#fff6ed" : "#f0f3f8"} stroke={agent.color} strokeWidth="1.5" />
            <text x={lx} y={ly + 4} textAnchor="middle" fontSize="9.5" fontFamily="DM Sans,system-ui" fontWeight="500" letterSpacing="0.05em" fill="#2a3852" fillOpacity="0.7">
              {agent.label.toUpperCase()}
            </text>
          </g>
        );
      })}
      {[30, 350, 310, 90].map((deg, i) => {
        const rd = (deg * Math.PI) / 180;
        return <circle key={i} cx={cx + 155 * Math.cos(rd)} cy={cy + 155 * Math.sin(rd)} r={2} fill="#d47a03" fillOpacity="0.2" />;
      })}
    </svg>
  );
}