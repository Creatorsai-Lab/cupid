import Link from "next/link";

const AGENTS = [
  {
    index: "01",
    name: "Persona",
    description:
      "Learns your voice from writing samples. Builds a living model of your tone, vocabulary, and domain depth.",
  },
  {
    index: "02",
    name: "Research",
    description:
      "Finds angles, sources, and ideas tailored to your expertise. Runs autonomously or on-demand.",
  },
  {
    index: "03",
    name: "Trend Intelligence",
    description:
      "Monitors Reddit, HackerNews, and RSS feeds in your domain. Surfaces what is rising before it peaks.",
  },
  {
    index: "04",
    name: "Composer",
    description:
      "Assembles everything into platform-specific posts. Runs a fidelity check — if it does not sound like you, it regenerates.",
  },
];

const TRAITS = [
  { label: "Always sounds like you", sub: "Not like AI, not like a template." },
  { label: "Platform-aware formatting", sub: "LinkedIn, X, Threads, Reddit." },
  { label: "Trend-to-post in minutes", sub: "From signal to publish, automated." },
  { label: "Privacy-first by default", sub: "Your persona data stays yours." },
];

export default function HomePage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        backgroundColor: "var(--color-bg)",
        overflowX: "hidden",
      }}
    >
      {/* ─── HERO ─────────────────────────────────────────────── */}
      <section
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "7rem 1.5rem 6rem",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "4rem",
          alignItems: "center",
        }}
        className="hero-section"
      >
        {/* Left — Copy */}
        <div>
          <p
            style={{
              fontSize: "0.78rem",
              fontWeight: 500,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--color-primary)",
              marginBottom: "1.5rem",
              fontFamily: "var(--font-body)",
            }}
            className="animate-float-up"
          >
            Multi-agent social intelligence
          </p>

          <h1
            style={{
              fontSize: "clamp(2.6rem, 5vw, 4rem)",
              fontFamily: "var(--font-display)",
              fontWeight: 400,
              lineHeight: 1.1,
              color: "var(--color-text)",
              marginBottom: "1.75rem",
              letterSpacing: "-0.02em",
            }}
            className="animate-float-up"
          >
            Post like yourself,
            <br />
            <em style={{ color: "var(--color-primary)", fontStyle: "italic" }}>
              not like everyone else.
            </em>
          </h1>

          <p
            style={{
              fontSize: "1.05rem",
              color: "var(--color-text-muted)",
              lineHeight: 1.75,
              maxWidth: "440px",
              marginBottom: "2.5rem",
              fontFamily: "var(--font-body)",
            }}
            className="animate-float-up"
          >
            Cupid learns your voice, tracks what is trending in your field, and
            composes posts that sound authentically like you — across every
            platform, on schedule.
          </p>

          <div
            style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}
            className="animate-float-up"
          >
            <Link href="/register" className="btn-primary">Start for free</Link>
            <Link href="#how-it-works" className="btn-secondary">See how it works</Link>

          </div>
        </div>

        {/* Right — Agent Visualization */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            height: "380px",
          }}
          className="animate-fade-in"
        >
          <AgentOrbit />
        </div>
      </section>

      {/* ─── DIVIDER ──────────────────────────────────────────── */}
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 1.5rem",
        }}
      >
        <div
          style={{ height: "1px", backgroundColor: "var(--color-border)" }}
        />
      </div>

      {/* ─── AGENTS ───────────────────────────────────────────── */}
      <section
        id="how-it-works"
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "6rem 1.5rem",
        }}
      >
        <div style={{ marginBottom: "3.5rem" }}>
          <p
            style={{
              fontSize: "0.78rem",
              fontWeight: 500,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--color-primary)",
              marginBottom: "0.75rem",
              fontFamily: "var(--font-body)",
            }}
          >
            The pipeline
          </p>
          <h2
            style={{
              fontSize: "clamp(1.8rem, 3vw, 2.6rem)",
              fontFamily: "var(--font-display)",
              fontWeight: 400,
              color: "var(--color-text)",
              letterSpacing: "-0.02em",
            }}
          >
            Four agents. One authentic voice.
          </h2>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1px",
            backgroundColor: "var(--color-border)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            overflow: "hidden",
          }}
        >
          {AGENTS.map((agent) => (
            <div
              key={agent.index}
              style={{
                backgroundColor: "var(--color-bg-surface)",
                padding: "2rem 1.75rem",
                position: "relative",
              }}
            >
              <span
                style={{
                  display: "block",
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  color: "var(--color-primary)",
                  fontFamily: "var(--font-body)",
                  marginBottom: "1rem",
                }}
              >
                {agent.index}
              </span>
              <h3
                style={{
                  fontSize: "1.15rem",
                  fontFamily: "var(--font-display)",
                  fontWeight: 400,
                  color: "var(--color-text)",
                  marginBottom: "0.75rem",
                  letterSpacing: "-0.01em",
                }}
              >
                {agent.name}
              </h3>
              <p
                style={{
                  fontSize: "0.88rem",
                  color: "var(--color-text-muted)",
                  lineHeight: 1.7,
                  fontFamily: "var(--font-body)",
                }}
              >
                {agent.description}
              </p>
              {/* Connector arrow — hidden on last item */}
              {agent.index !== "04" && (
                <div
                  style={{
                    position: "absolute",
                    right: "-10px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    width: "18px",
                    height: "18px",
                    backgroundColor: "var(--color-primary-subtle)",
                    border: "1px solid var(--color-primary)",
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 2,
                    fontSize: "9px",
                    color: "var(--color-primary)",
                  }}
                >
                  →
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ─── TRAITS ───────────────────────────────────────────── */}
      <section
        style={{
          backgroundColor: "pink",
          borderTop: "1px solid var(--color-border)",
          borderBottom: "1px solid var(--color-border)",
          padding: "5rem 1.5rem",
        }}
      >
        <div
          style={{
            maxWidth: "1200px",
            margin: "0 auto",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "2.5rem",
          }}
        >
          {TRAITS.map((trait) => (
            <div key={trait.label}>
              <div
                style={{
                  width: "32px",
                  height: "2px",
                  backgroundColor: "var(--color-primary)",
                  marginBottom: "1rem",
                  borderRadius: "2px",
                }}
              />
              <h3
                style={{
                  fontSize: "1rem",
                  fontFamily: "var(--font-display)",
                  fontWeight: 400,
                  color: "var(--color-text)",
                  marginBottom: "0.4rem",
                }}
              >
                {trait.label}
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--color-text-muted)",
                  fontFamily: "var(--font-body)",
                }}
              >
                {trait.sub}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── CTA ──────────────────────────────────────────────── */}
      <section
        style={{
          maxWidth: "760px",
          margin: "0 auto",
          padding: "8rem 1.5rem",
          textAlign: "center",
        }}
      >
        <h2>Your audience is already<br /><em>paying attention.</em></h2>
        <p className="text-muted-foreground mb-6 font-body">Set up your persona once. Let Cupid handle the rest.</p>
        <Link href="/register" className="btn-primary">Create your persona</Link>
      </section>



      {/* ─── RESPONSIVE STYLES ────────────────────────────────── */}
      <style>{`
        @media (max-width: 768px) {
          .hero-section {
            grid-template-columns: 1fr !important;
            padding-top: 4rem !important;
            padding-bottom: 3rem !important;
            gap: 3rem !important;
          }
        }
      `}</style>
    </main >
  );
}

/* ─── Agent Orbit SVG Visualization ───────────────────────── */
function AgentOrbit() {
  const agents = [
    { label: "Persona", angle: 270, color: "#d47a03" },
    { label: "Research", angle: 0, color: "#2a3852" },
    { label: "Trend", angle: 90, color: "#d47a03" },
    { label: "Composer", angle: 180, color: "#2a3852" },
  ];

  const cx = 190;
  const cy = 190;
  const r = 110;

  return (
    <svg
      width="380"
      height="380"
      viewBox="0 0 380 380"
      fill="none"
      style={{ maxWidth: "100%", height: "auto" }}
    >
      {/* Orbit ring */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        stroke="var(--secondary)"
        strokeWidth="1"
        strokeDasharray="4 6"
      />

      {/* Outer pulse ring */}
      <circle
        cx={cx}
        cy={cy}
        r={r + 28}
        stroke="#d47a03"
        strokeWidth="0.5"
        strokeOpacity="0.2"
      />

      {/* Center node */}
      <circle cx={cx} cy={cy} r={28} fill="#fff6ed" stroke="#d47a03" strokeWidth="1" />
      <circle cx={cx} cy={cy} r={20} fill="#d47a03" fillOpacity="0.08" />
      <text
        x={cx}
        y={cy + 4}
        textAnchor="middle"
        fontSize="9"
        fontFamily="DM Sans, system-ui"
        fontWeight="500"
        letterSpacing="0.08em"
        fill="#d47a03"
      >
        CUPID
      </text>

      {/* Agent nodes */}
      {agents.map((agent) => {
        const rad = (agent.angle * Math.PI) / 180;
        const nx = cx + r * Math.cos(rad);
        const ny = cy + r * Math.sin(rad);

        /* Label position — push outward from center */
        const lx = cx + (r + 46) * Math.cos(rad);
        const ly = cy + (r + 46) * Math.sin(rad);

        return (
          <g key={agent.label}>
            {/* Connector line */}
            <line
              x1={cx}
              y1={cy}
              x2={nx}
              y2={ny}
              stroke={agent.color}
              strokeWidth="0.75"
              strokeOpacity="0.25"
              strokeDasharray="3 4"
            />

            {/* Node pulse halo */}
            <circle
              cx={nx}
              cy={ny}
              r={18}
              fill={agent.color}
              fillOpacity="0.06"
              style={{
                animation: "pulse-ring 3s ease-in-out infinite",
                animationDelay: `${agents.indexOf(agent) * 0.6}s`,
                transformOrigin: `${nx}px ${ny}px`,
              }}
            />

            {/* Node circle */}
            <circle
              cx={nx}
              cy={ny}
              r={11}
              fill={agent.color === "#d47a03" ? "#fff6ed" : "#f0f3f8"}
              stroke={agent.color}
              strokeWidth="1.5"
            />

            {/* Label */}
            <text
              x={lx}
              y={ly + 4}
              textAnchor="middle"
              fontSize="9.5"
              fontFamily="DM Sans, system-ui"
              fontWeight="500"
              letterSpacing="0.05em"
              fill="#2a3852"
              fillOpacity="0.7"
            >
              {agent.label.toUpperCase()}
            </text>
          </g>
        );
      })}

      {/* Decorative corner dots */}
      {[30, 350, 310, 90].map((deg, i) => {
        const rd = (deg * Math.PI) / 180;
        return (
          <circle
            key={i}
            cx={cx + 155 * Math.cos(rd)}
            cy={cy + 155 * Math.sin(rd)}
            r={2}
            fill="#d47a03"
            fillOpacity="0.2"
          />
        );
      })}
    </svg>
  );
}