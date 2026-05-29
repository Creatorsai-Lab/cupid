"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { type LucideIcon,
  ChartColumn , Waves, ScanSearch, Flame, Layers, Brain, Edit3, ShieldCheck, CircleDollarSign,
  Code2, Heart, Smile, GraduationCap, UserCheck, Mail, FileText, Search, Fingerprint, PenTool, CalendarClock, Send, User, Sparkles
} from "lucide-react";
import {
  XCard, LinkedInCard, InstagramCard, FacebookCard,
  YouTubeCard, YouTubeShortsCard, PollCard,
} from "@/components/SocialMediaCards";
import Footer from "@/components/Footer";

const PIPELINE_STAGES = [
  {
    key: "input",
    label: "Input",
    sub: "Your voice & samples",
    desc: "You feed Cupid writing samples and a topic. It anchors to who you are before anything moves.",
    icon: FileText,
  },
  {
    key: "research",
    label: "Research",
    sub: "Angles & sources",
    desc: "The Research agent scans your niche — finds angles, evidence, and the framing that fits your depth.",
    icon: Search,
  },
  {
    key: "personalization",
    label: "Personalization",
    sub: "Tuned to your persona",
    desc: "Findings pass through your living persona model: tone, vocabulary, and the way you actually think.",
    icon: User,
  },
  {
    key: "creation",
    label: "Creation",
    sub: "Platform-native drafts",
    desc: "The Composer assembles posts per platform, then runs a fidelity check — if it isn't you, it rewrites.",
    icon: Sparkles,
  },
  {
    key: "publish",
    label: "Publish / Schedule",
    sub: "On your timeline",
    desc: "Approved posts ship now or queue to your calendar — every platform, on your schedule.",
    icon: Send,
  },
];


const CREATOR_BUSINESS_TYPES = [
  { icon: Code2, label: "Influencers & Celebrities", sub: "Engineers shipping content alongside code." },
  { icon: Heart, label: "Community Builders", sub: "Aesthetic-led, trend-sensitive feeds." },
  { icon: Smile, label: "Side Hustler", sub: "Voice-led, timing-driven posts." },
];
const CAPABILITIES = [
  { icon: ScanSearch, label: "Personalized Content Research", sub: "Sources tailored to your domain — not generic web noise." },
  { icon: Flame, label: "Trends Recommendation", sub: "Reddit, HN, RSS — signal to published in minutes." },
  { icon: Layers, label: "Platform-native Drafts", sub: "Twitter, LinkedIn, Instagram, YouTube — each properly formatted." },
  { icon: Brain, label: "Persona Memory", sub: "Your voice, stored privately and refined as you keep writing." },
  { icon: CircleDollarSign, label: "Monitization Coach", sub: "A live read on which revenue streams fit your tier and niche." },
  { icon: ChartColumn, label: "Real-time Insights", sub: "Followers, views, top content — all the signal, none of the dashboards." },
];

//  HERO SECTION - CTA and Pipeline
export function Hero() {
  const [active, setActive] = useState(0);
  const [hovered, setHovered] = useState<number | null>(null);
  const timer = useRef<NodeJS.Timeout | null>(null);

  // Auto-advance the active stage in sync with the traveling pulse (13s total loop / 5 stages = 2600ms)
  useEffect(() => {
    if (hovered !== null) return;
    timer.current = setInterval(() => {
      setActive((i) => (i + 1) % PIPELINE_STAGES.length);
    }, 2600);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [hovered]);

  const current = hovered !== null ? hovered : active;

  return (
    <section id="pipeline" className="mx-auto max-w-6xl px-4 py-12 md:py-20 text-(--color-text)">
      <PipelineKeyframes />
      <div className="mb-16 flex flex-col items-center text-center">
        <h1 className="text-[clamp(4.5rem,11vw,8rem)] leading-[0.92] font-[family-name:var(--font-display)]">
          Cupid
        </h1>    
        <h2 className="font-[family-name:var(--font-display)] animated-gradient-text italic text-xl md:text-2xl mt-2 tracking-tight">
          A complete AI agents suite for content creation & influencers
        </h2>    
        <p className="text-[15px] text-muted-foreground leading-relaxed max-w-2xl mt-4">
          Cupid agents learn your voice, track what's trending in your niche, and ship posts that 
          sound authentically like you — across every platform, on your schedule.
        </p>
        <div className="flex gap-3 flex-wrap justify-center pt-5">
          <Link href="/register" className="btn-primary">Start for free</Link>
          <Link href="#agents" className="btn-secondary">See how it works</Link>
        </div>
      </div>

      {/* ── ANIMATED TRACK PIPELINE ── */}
      <div className="relative max-w-[1080px] mx-auto px-1 md:px-0">
        
        {/* Rail Base & Progress Timelines */}
        <div className="absolute top-[28px] left-[28px] right-[28px] h-[2px] bg-(--color-border) rounded-full hidden md:block" aria-hidden="true">
          <span className="absolute inset-0 origin-left bg-gradient-to-r from-(--color-primary) to-(--color-primary-dark) rounded-full animate-[cp-fill_13s_linear_infinite]" />
          <span className="absolute top-1/2 w-[10px] h-[10px] -mt-[5px] -ml-[5px] rounded-full bg-(--color-primary) shadow-[0_0_0_5px_rgba(199,93,58,0.18),0_0_14px_2px_rgba(199,93,58,0.45)] animate-[cp-travel_13s_linear_infinite]" />
        </div>

        {/* Mobile Rail (Vertical Layout Toggle) */}
        <div className="absolute top-[28px] bottom-[28px] left-[28px] w-[2px] bg-(--color-border) rounded-full block md:hidden" aria-hidden="true">
          <span className="absolute inset-0 origin-top bg-gradient-to-b from-(--color-primary) to-(--color-primary-dark) rounded-full animate-[cp-fill-v_13s_linear_infinite]" />
          <span className="absolute left-1/2 w-[10px] h-[10px] -mt-[5px] -ml-[5px] rounded-full bg-(--color-primary) shadow-[0_0_0_5px_rgba(199,93,58,0.18),0_0_14px_2px_rgba(199,93,58,0.45)] animate-[cp-travel-v_13s_linear_infinite]" />
        </div>

        {/* Stages Map List */}
        <ol className="relative flex flex-col md:flex-row justify-between gap-8 md:gap-2 list-none p-0 m-0">
          {PIPELINE_STAGES.map((s, i) => {
            const Icon = s.icon;
            const isCurrent = i === current;
            const isDone = i < current;

            return (
              <li
                key={s.key}
                tabIndex={0}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(i)}
                onBlur={() => setHovered(null)}
                className={`group flex flex-1 flex-row md:flex-col items-center text-left md:text-center gap-4 md:gap-[0.85rem] cursor-pointer outline-none min-w-0`}
              >
                {/* Node Structure */}
                <div className="relative w-14 h-14 flex-shrink-0 grid place-items-center">
                  
                  {/* Outer Pulsing Active Ring */}
                  <span className={`absolute -inset-[6px] rounded-full border border-transparent transition-all duration-[450ms] ${
                    isCurrent ? "opacity-100 border-(--color-primary)/35 animate-[cp-ring_2.4s_ease-out_infinite]" : "opacity-0"
                  }`} />
                  
                  {/* Central Node Circle */}
                  <span className={`relative z-10 w-14 h-14 flex items-center justify-center rounded-full border transition-all duration-[450ms] ease-out ${
                    isCurrent
                      ? "text-white bg-(--color-primary) border-(--color-primary) scale-[1.08] shadow-[0_8px_22px_rgba(199,93,58,0.28)]"
                      : isDone
                      ? "text-(--color-primary) border-(--color-primary) bg-white dark:bg-zinc-900"
                      : "text-(--color-subtle) border-(--color-border) bg-white dark:bg-zinc-900"
                  }`}>
                    <Icon className="w-5 h-5" strokeWidth={1.75} />
                  </span>

                  {/* Sequential Numeric Badge */}
                  <span className={`absolute z-20 -top-1 -right-1 text-[9px] font-bold w-[18px] h-[18px] flex items-center justify-center rounded-full border transition-all duration-[450ms] ${
                    isCurrent
                      ? "text-white bg-(--color-primary-dark) border-(--color-primary-dark)"
                      : isDone
                      ? "text-(--color-primary) border-(--color-primary) bg-(--color-background)"
                      : "text-(--color-subtle) border-(--color-border) bg-(--color-background)"
                  }`}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>

                {/* Text Description Copy */}
                <div className="min-w-0">
                  <p className={`font-[family-name:var(--font-display)] text-[clamp(0.95rem,1.6vw,1.1rem)] font-normal m-0 leading-tight transition-colors duration-400 ${
                    isCurrent ? "text-(--color-primary-dark)" : "text-(--color-text)"
                  }`}>
                    {s.label}
                  </p>
                  <p className="text-[11.5px] md:text-[12.5px] text-muted-foreground mt-1 m-0 leading-snug">
                    {s.sub}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      {/* ── DETAIL EXPLANATION PANEL ── */}
      <div 
        key={current} 
        className="max-w-[1080px] mx-auto mt-10 md:mt-14 flex items-start gap-4 p-5 md:p-7 bg-white dark:bg-zinc-900 border border-(--color-border) rounded-[14px] shadow-sm animate-[cp-detail-in_0.5s_cubic-bezier(0.22,1,0.36,1)_both]"
      >
        <span className="font-[family-name:var(--font-display)] text-[clamp(1.6rem,4vw,2.2rem)] text-(--color-primary) line-height-1 shrink-0 font-normal">
          {String(current + 1).padStart(2, "0")}
          <span className="text-[0.55em] text-(--color-subtle)">/05</span>
        </span>
        <p className="text-[clamp(0.9rem,2vw,1.02rem)] leading-relaxed text-muted-foreground mt-[0.15rem] m-0 max-w-[52ch]">
          {PIPELINE_STAGES[current].desc}
        </p>
      </div>
    </section>
  );
}

/**
 * Clean injection component handling non-trivial multi-stage keyframe animations
 * that are outside normal Tailwind atomic configurations.
 */
function PipelineKeyframes() {
  return (
    <style dangerouslySetInnerHTML={{ __html: `
      @keyframes cp-fill {
        0%   { transform: scaleX(0); }
        90%  { transform: scaleX(1); }
        100% { transform: scaleX(1); }
      }
      @keyframes cp-travel {
        0%   { left: 0%;   opacity: 0; }
        4%   { opacity: 1; }
        90%  { left: 100%; opacity: 1; }
        96%  { left: 100%; opacity: 0; }
        100% { left: 100%; opacity: 0; }
      }
      @keyframes cp-fill-v {
        0%   { transform: scaleY(0); }
        90%  { transform: scaleY(1); }
        100% { transform: scaleY(1); }
      }
      @keyframes cp-travel-v {
        0%   { top: 0%;   opacity: 0; }
        4%   { opacity: 1; }
        90%  { top: 100%; opacity: 1; }
        96%  { top: 100%; opacity: 0; }
        100% { top: 100%; opacity: 0; }
      }
      @keyframes cp-ring {
        0%   { transform: scale(1);   opacity: .7; }
        70%  { transform: scale(1.5); opacity: 0; }
        100% { transform: scale(1.5); opacity: 0; }
      }
      @keyframes cp-detail-in {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @media (prefers-reduced-motion: reduce) {
        .animate-\\[cp-fill_13s_linear_infinite\\],
        .animate-\\[cp-travel_13s_linear_infinite\\],
        .animate-\\[cp-fill-v_13s_linear_infinite\\],
        .animate-\\[cp-travel-v_13s_linear_infinite\\],
        .animate-\\[cp-ring_2.4s_ease-out_infinite\\] {
          animation: none !important;
          transform: scale(1) !important;
          opacity: 1 !important;
        }
      }
    `}} />
  );
}

// AGENTS SECTION

function AgentsSection() {
  return (
    <section id="agents" className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-24 grid lg:grid-cols-2 gap-16 items-center">
          <div className="flex justify-center order-2 lg:order-1">
            <AgentOrbit />
          </div>
          <div className="order-1 lg:order-2">
            <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-primary mb-3">
              The Architecture
            </p>
            <h2 className="text-[clamp(1.8rem,3vw,2.4rem)] font-normal tracking-tight text-foreground mb-8 leading-[1.1] font-[family-name:var(--font-display)]">
              Team of Agents Swarm at your fingertips
            </h2>
            <p>Our agents are smart, Our agents are smart, Our agents are smart, Our agents are smart, Our agents are smart, Our agents are smart, Our agents are smart, Our agents are smart, Our agents are smart, Our agents are smart, </p>
          </div>
        </div>
      </section>
  );
}


function PostsPreview() {
  return (
    <section id="examples" className="border-t border-border bg-muted/20">
      <div className="max-w-6xl mx-auto px-6 py-24">
      <h2 className="text-[clamp(1.8rem,3vw,2.4rem)] tracking-tight mb-3 text-center">Posts that already sound like you</h2>
        <p className="text-center mb-14">Intelligence personalized to each social media platform formats and tone</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <XCard name="Adya Prasad" handle="adyaprasad" content="Just shipped persona fidelity scoring for Cupid." />
                  <FacebookCard name="Rakul Bansal" content="Just shipped persona fidelity scoring for Cupid." />
                  <LinkedInCard name="Rakul Bansal" content="Just shipped persona fidelity scoring for Cupid." />
                  <InstagramCard
                    name="Rakul Bansal"
                    content="Just shipped persona fidelity scoring for Cupid."
                    mediaUrl="/public/media/boy_profile.webp"
                  />
                  <YouTubeShortsCard name="Adya Prasad" content="Cute Couple Status." />
                  <YouTubeShortsCard
                    name="Adya Prasad"
                    handle="adyaprasad"
                    content="Just shipped persona fidelity scoring for Cupid AI."
                    mediaUrl="/short-thumbnail.jpg"
                  />
                  <YouTubeCard name="Rakul Bansal" content="Just shipped persona fidelity scoring for Cupid." />
                  <PollCard
                    name="Adya Prasad"
                    handle="adyaprasad"
                    question="Which framework should I use for Cupid's agent layer?"
                    options={["LangGraph", "CrewAI", "AutoGen", "Build from scratch"]}
                    timeLeft="18h left"
                  />
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
    </div>
    </section>
  );
}


function AgentOrbit() {
  const agents = [
    { label: "Persona", angle: 270, color: "#af6d58" },
    { label: "Research", angle: 0, color: "#af6d58" },
    { label: "Trend", angle: 90, color: "#af6d58" },
    { label: "Composer", angle: 180, color: "#af6d58" },
  ];
  const cx = 190, cy = 190, r = 110;

  return (
    <svg width="500" height="500" viewBox="0 0 380 380" fill="none" className="max-w-full h-auto">
      <circle cx={cx} cy={cy} r={r} stroke="#645A51" strokeWidth="1" strokeDasharray="4 6" />
      <circle cx={cx} cy={cy} r={r + 28} stroke="#c58772" strokeWidth="0.5" strokeOpacity="0.3" />
      <circle cx={cx} cy={cy} r={28} fill="#fff6ed" stroke="#C75D3A" strokeWidth="1" />
      <circle cx={cx} cy={cy} r={20} fill="#C75D3A" />
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize="9" fontFamily="DM Sans,system-ui" fontWeight="500" letterSpacing="0.08em" fill="#ffffff">
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
            <circle cx={nx} cy={ny} r={11} fill={agent.color === "#d47a03" ? "#f0e0d1" : "#f0f3f8"} stroke={agent.color} strokeWidth="1.5" />
            <text x={lx} y={ly + 4} textAnchor="middle" fontSize="9.5" fontFamily="DM Sans,system-ui" fontWeight="500" letterSpacing="0.05em" fill="#522a48" fillOpacity="0.7">
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


function Description(){
  return(
  <section className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-24 lg:py-32 grid lg:grid-cols-[2fr_3fr] gap-12 lg:gap-20">
          <div className="space-y-7 lg:sticky lg:top-24 lg:self-start">
            <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-primary">
              The product
            </p>
            <h2 className="text-[clamp(1.9rem,3.6vw,2.8rem)] font-normal tracking-tight leading-[1.08] font-[family-name:var(--font-display)] text-foreground">
              An end-to-end agent suite engineered to amplify your <em className="animated-gradient-text">authentic voice</em>.
            </h2>
            <div className="space-y-5 text-[15px] text-muted-foreground leading-relaxed">
              <p>
                Our agents learn how you actually write — your sentence rhythm,
                the jokes you'd make, the words you'd never use. They research
                what your audience cares about. Then they draft, format, and
                ship.
              </p>
              <p>
                Set up your persona once. Let trend ingestion run in the
                background. Wake up to drafts that sound exactly like you.
              </p>
            </div>
          </div>

          <div className="space-y-16">
            <div>
              <h3 className="text-lg font-medium text-foreground mb-8 font-[family-name:var(--font-display)]">
                Agents that work the way creators think.
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-10">
                {CAPABILITIES.map((f) => (
                  <div key={f.label} className="group">
                    <div className="w-9 h-9 rounded-lg border border-primary/15 bg-primary/5 flex items-center justify-center mb-3 group-hover:bg-primary/10 group-hover:border-primary/25 transition-colors">
                      <f.icon className="w-4 h-4 text-primary" strokeWidth={1.75} />
                    </div>
                    <p className="text-[13.5px] font-medium text-foreground mb-1.5 leading-snug font-[family-name:var(--font-display)]">
                      {f.label}
                    </p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {f.sub}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-foreground mb-8 font-[family-name:var(--font-display)]">
                Built for every kind of creator.
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-10">
                {CREATOR_BUSINESS_TYPES.map((c) => (
                  <div key={c.label} className="group">
                    <div className="w-9 h-9 rounded-lg border border-primary/15 bg-primary/5 flex items-center justify-center mb-3 group-hover:bg-primary/10 group-hover:border-primary/25 transition-colors">
                      <c.icon className="w-4 h-4 text-primary" strokeWidth={1.75} />
                    </div>
                    <p className="text-[13.5px] font-medium text-foreground mb-1.5 leading-snug font-[family-name:var(--font-display)]">
                      {c.label}
                    </p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {c.sub}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
  );
}

export default function HomePage() {
  return (
    <main className="min-h-screen overflow-x-hidden bg-background text-text antialiased">
      <Hero />
      <AgentsSection />
      <PostsPreview />
      <Description/>
      <Footer />
    </main>
  );
}