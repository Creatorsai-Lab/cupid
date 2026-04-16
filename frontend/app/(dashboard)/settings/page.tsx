"use client";

import { useState, useEffect } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuthStore } from "@/lib/store";
import { User, Sparkles, HelpCircle, Settings, Workflow } from "lucide-react";
import { authApi, profileApi } from "@/lib/api";
import { useRouter } from "next/navigation";

const TABS = [
  { id: "personalization", label: "Personalization", icon: User },
  { id: "integration", label: "Integration", icon: Workflow },
  { id: "settings", label: "Settings", icon: Settings },
  { id: "plan", label: "Plan", icon: Sparkles },
  { id: "help", label: "Help", icon: HelpCircle }

] as const;


type TabId = (typeof TABS)[number]["id"];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("personalization");
  const { user } = useAuthStore();

  return (
    <ProtectedRoute>
      <main style={{
        minHeight: "calc(100vh - 60px)",
        backgroundColor: "var(--color-background)",
        padding: "2rem 1.5rem",
      }}>
        <div style={{ maxWidth: "800px", margin: "0 auto" }}>
          {/* Page header */}
          <div style={{ marginBottom: "2rem" }}>
            <h1 style={{
              fontFamily: "var(--font-display)",
              fontSize: "1.8rem",
              fontWeight: 400,
              color: "var(--color-text)",
              letterSpacing: "-0.02em",
            }}>
              Settings
            </h1>
            <p style={{
              fontSize: "0.88rem",
              color: "var(--color-muted)",
              fontFamily: "var(--font-body)",
              marginTop: "0.25rem",
            }}>
              Manage your profile and preferences
            </p>
          </div>

          {/* Tabs */}
          <div style={{
            display: "flex",
            gap: "0.25rem",
            borderBottom: "1px solid var(--color-border)",
            marginBottom: "2rem",
          }}>
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.6rem 1rem",
                  fontSize: "0.85rem",
                  fontWeight: activeTab === id ? 600 : 400,
                  fontFamily: "var(--font-body)",
                  color: activeTab === id ? "var(--color-primary)" : "var(--color-muted)",
                  backgroundColor: "transparent",
                  border: "none",
                  borderBottom: activeTab === id ? "2px solid var(--color-primary)" : "2px solid transparent",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  marginBottom: "-1px",
                }}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {activeTab === "personalization" && <PersonalizationTab userName={user?.full_name} userEmail={user?.email} />}
          {activeTab === "plan" && <PlanTab />}
          {activeTab === "settings" && <SettingsTab />}
          {activeTab === "help" && <HelpTab />}
        </div>
      </main>
    </ProtectedRoute>
  );
}

/* PERSONALIZATION TAB */
const NICHES = [
  { group: "Technology", items: ["AI / Machine Learning", "Software Engineering", "Cybersecurity", "Web Development", "Mobile Development", "Data Science", "Cloud Computing", "Blockchain / Web3", "Tech News & Reviews", "Gaming", "VR / AR"] },
  { group: "Business & Career", items: ["Entrepreneurship", "Startups", "Marketing", "Personal Finance", "Investing & Stocks", "Crypto & DeFi", "Real Estate", "E-commerce", "Freelancing", "Career Growth", "Productivity", "Leadership"] },
  { group: "Creator Economy", items: ["Content Creation", "YouTube Strategy", "Newsletter Writing", "Podcasting", "Copywriting", "Personal Branding", "Social Media Growth", "Photography", "Videography", "Graphic Design", "UI/UX Design"] },
  { group: "Health & Lifestyle", items: ["Fitness & Gym", "Mental Health", "Yoga & Meditation", "Nutrition & Diet", "Running & Endurance", "Sports", "Biohacking", "Parenting", "Relationships", "Minimalism", "Self-improvement"] },
  { group: "Education", items: ["Online Learning", "Study Tips", "Language Learning", "Mathematics", "Science & Research", "History", "Philosophy", "Book Summaries", "Skill Development"] },
  { group: "Entertainment", items: ["Comedy & Humor", "Movie & TV Reviews", "Music", "Pop Culture", "Anime & Manga", "Fashion", "Beauty & Skincare", "Travel", "Food & Cooking", "Pets & Animals", "Art & Illustration"] },
  { group: "Niche & Micro", items: ["Solopreneurship", "No-Code Tools", "Research & Academia", "Climate & Sustainability", "Politics & Policy", "Spirituality", "True Crime", "Expat Life", "LGBTQ+", "Disability Advocacy"] },
];

const CONTENT_GOAL = [
  ["personal_brand", "Build personal brand"],
  ["business_marketing", "Market my business"],
  ["get_clients", "Get clients or consulting work"],
  ["teach", "Teach and share knowledge"],
  ["get_job", "Get a job or attract recruiters"],
  ["grow_audience", "Grow an audience"],
  ["monetize", "Monetize content"],
  ["community", "Build a community"],
  ["thought_leadership", "Establish thought leadership"],
];

const AGE_GROUPS = [
  ["gen_z", "Gen Z — 18 to 26"],
  ["millennials", "Millennials — 27 to 42"],
  ["gen_x", "Gen X — 43 to 58"],
  ["boomers", "Boomers — 59 and above"],
  ["all_ages", "All ages"],
];

const COUNTRIES = [
  "India", "United States", "United Kingdom", "Canada", "Australia",
  "Germany", "France", "Brazil", "China", "South Africa",
  "Indonesia", "Pakistan", "Russia", "Mexico", "Japan",
  "South Korea", "UAE", "Saudi Arabia", "Singapore", "Spain",
];

const AUDIENCES = [
  ["students", "Students & fresh graduates"],
  ["professionals", "Working professionals"],
  ["developers", "Developers & engineers"],
  ["creatives", "Marketers & creatives"],
  ["founders", "Founders & entrepreneurs"],
  ["researchers", "Researchers & academics"],
  ["finance", "Investors & finance people"],
  ["parents", "Homemakers & parents"],
  ["fitness", "Sports & fitness enthusiasts"],
  ["general", "General public"],
  ["kids", "playful and happy"],
];

const CONTENT_INTENTS = [
  ["educational", "teach concepts and how-tos"],
  ["motivational", "inspire action and mindset"],
  ["entertaining", "make audience laugh and fresh"],
  ["storytelling", "telling story imagination"],
  ["humorous", "witty and lighthearted"],
  ["insightful", "deep analysis and hot takes"],
  ["news", "react to current events"],
  ["promotional", "sell products or services"],
];

// ─── Types ───────────────────────────────────────────────────

interface PersonalizationForm {
  name: string;
  nickname: string,
  bio: string;
  content_niche: string;
  content_goal: string;
  content_intent: string;
  target_age_group: string;
  target_country: string;
  target_audience: string;
  usp: string;
}

const EMPTY: PersonalizationForm = {
  name: "", nickname:"", bio: "",
  content_niche: "", content_goal: "", content_intent: "",
  target_age_group: "", target_country: "",
  target_audience: "", usp: "",
};

// ─── Shared class strings ─────────────────────────────────────

const cx = {
  input: "w-full h-10 px-3 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#d47a03] transition-shadow",
  select: "w-full h-10 px-3 rounded-lg border border-border bg-background text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[#d47a03] cursor-pointer transition-shadow",
  textarea: "w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#d47a03] resize-none transition-shadow",
};

// ─── Sub-components ───────────────────────────────────────────

function Section({ title, hint, children }: {
  title: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      <div>
        <h3 className="text-base font-normal text-foreground" style={{ fontFamily: "var(--font-display)" }}>
          {title}
        </h3>
        <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>
      </div>
      {children}
    </div>
  );
}

function Field({ label, children, full }: {
  label: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <label className="block text-xs font-medium text-foreground mb-1.5">
        {label}
      </label>
      {children}
    </div>
  );
}
function PersonalizationTab({
  userName,
  userEmail,
}: {
  userName?: string;
  userEmail?: string;
}) {
  const [form, setForm] = useState<PersonalizationForm>({ ...EMPTY, name: userName ?? "" });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  const set = (key: keyof PersonalizationForm) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm((p) => ({ ...p, [key]: e.target.value }));

  useEffect(() => {
    const load = async () => {
      try {
        const res = await profileApi.get();
        const data = res.data;
        if (data) {
          setForm((p) => ({
            ...p,
            ...data,
            name: data.name ?? p.name,
            nickname: data.nickname ?? "",
            bio: data.bio ?? "",
            content_niche: data.content_niche ?? "",
            content_goal: data.content_goal ?? "",
            content_intent: data.content_intent ?? "",
            target_age_group: data.target_age_group ?? "",
            target_country: data.target_country ?? "",
            target_audience: data.target_audience ?? "",
            usp: data.usp ?? "",
          }));
        }
      } catch {
        // no profile yet
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await profileApi.update(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return (
    <p className="text-sm text-muted-foreground">Loading profile...</p>
  );

  return (
    <div className="max-w-2xl space-y-5">

      {/* ── Identity ── */}
      <Section title="Identity" hint="Your basic profile used across the app.">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Full name">
            <input className={cx.input} value={form.name} onChange={set("name")} placeholder="Your full name" />
          </Field>
          <Field label="Email">
            <input className={`${cx.input} opacity-50 cursor-not-allowed`} value={userEmail ?? ""} disabled />
          </Field>
          <Field label="Bio" full>
            <textarea className={cx.textarea} rows={3} value={form.bio} onChange={set("bio")}
              placeholder="One or two sentences about yourself. This is used directly in your persona prompt." />
          </Field>
          <Field label="Nickname" full>
            <textarea className={cx.textarea} rows={3} value={form.nickname} onChange={set("nickname")}
              placeholder="What loving name should we call you?" />
          </Field>
        </div>
      </Section>

      {/* ── Content ── */}
      <Section title="Content Identity" hint="Tells Cupid what you create and why.">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Content niche" full>
            <select className={cx.select} value={form.content_niche} onChange={set("content_niche")}>
              <option value="">Select your niche</option>
              {NICHES.map(({ group, items }) => (
                <optgroup key={group} label={group}>
                  {items.map((item) => <option key={item} value={item}>{item}</option>)}
                </optgroup>
              ))}
            </select>
          </Field>
          <Field label="Primary goal">
            <select className={cx.select} value={form.content_goal} onChange={set("content_goal")}>
              <option value="">Select a goal</option>
              {CONTENT_GOAL.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Content intent">
            <select className={cx.select} value={form.content_intent} onChange={set("content_intent")}>
              <option value="">Select intent</option>
              {CONTENT_INTENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Unique value proposition (USP)" full>
            <textarea className={cx.textarea} rows={2} value={form.usp} onChange={set("usp")}
              placeholder='e.g. "I explain AI research in plain language — no PhD required."' />
          </Field>
        </div>
      </Section>

      {/* ── Audience ── */}
      <Section title="Target Audience" hint="Defines who Cupid writes for.">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Age group">
            <select className={cx.select} value={form.target_age_group} onChange={set("target_age_group")}>
              <option value="">Select age group</option>
              {AGE_GROUPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Target country">
            <select className={cx.select} value={form.target_country} onChange={set("target_country")}>
              <option value="">Select country</option>
              {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Audience type" full>
            <select className={cx.select} value={form.target_audience} onChange={set("target_audience")}>
              <option value="">Select your audience</option>
              {AUDIENCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
        </div>
      </Section>

      {/* ── Save ── */}
      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white bg-[#d47a03] hover:bg-[#b86a02] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? "Saving..." : "Save profile"}
        </button>
        {saved && (
          <span className="text-sm font-medium text-[#d47a03]">Saved</span>
        )}
      </div>

    </div>
  );
}


function SettingsTab() {
  const { clearUser } = useAuthStore();
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Even if API call fails, clear local state
    }
    clearUser();
    router.push("/login");
  };

  return (
    <div>
      <div style={{
        backgroundColor: "white",
        border: "1px solid var(--color-border)",
        borderRadius: "12px",
        padding: "1.5rem",
        marginBottom: "1.5rem",
      }}>
        <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", fontWeight: 400, marginBottom: "1rem", color: "var(--color-text)" }}>
          Appearance
        </h3>
        <p style={{ fontSize: "0.85rem", color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
          Theme: Light (dark mode coming soon)
        </p>
      </div>

      <div style={{
        backgroundColor: "white",
        border: "1px solid var(--color-border)",
        borderRadius: "12px",
        padding: "1.5rem",
      }}>
        <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", fontWeight: 400, marginBottom: "0.5rem", color: "#c0392b" }}>
          Danger Zone
        </h3>
        <p style={{ fontSize: "0.85rem", color: "var(--color-muted)", fontFamily: "var(--font-body)", marginBottom: "1rem" }}>
          Sign out of your Cupid account
        </p>
        <button
          onClick={handleLogout}
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "0.5rem 1.2rem",
            borderRadius: "8px",
            fontSize: "0.85rem",
            fontWeight: 500,
            fontFamily: "var(--font-body)",
            color: "#c0392b",
            backgroundColor: "transparent",
            border: "1px solid #c0392b",
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}


/* ━━━ Plan Tab ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

function PlanTab() {
  return (
    <div style={{
      backgroundColor: "white",
      border: "1px solid var(--color-border)",
      borderRadius: "12px",
      padding: "2rem",
    }}>
      <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", fontWeight: 400, marginBottom: "0.5rem" }}>
        Current Plan
      </h3>
      <div style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
        padding: "0.3rem 0.8rem",
        borderRadius: "20px",
        backgroundColor: "var(--color-primary)",
        color: "#fff",
        fontSize: "0.78rem",
        fontWeight: 600,
        fontFamily: "var(--font-body)",
        marginBottom: "1rem",
      }}>
        Free Tier
      </div>
      <p style={{ fontSize: "0.88rem", color: "var(--color-muted)", fontFamily: "var(--font-body)", lineHeight: 1.7 }}>
        You are on the free open-source plan. All core agent features are available with local LLM inference. No usage limits on self-hosted deployments.
      </p>
    </div>
  );
}


/* ━━━ Help Tab ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

function HelpTab() {
  const links = [
    { label: "Documentation", desc: "Setup guides and API reference", href: "#" },
    { label: "GitHub Repository", desc: "Source code, issues, and contributions", href: "#" },
    { label: "Community Discord", desc: "Chat with other Cupid users", href: "#" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {links.map((link) => (
        <a key={link.label} href={link.href} style={{
          display: "block",
          backgroundColor: "white",
          border: "1px solid var(--color-border)",
          borderRadius: "12px",
          padding: "1.25rem 1.5rem",
          transition: "border-color 0.15s ease",
        }}>
          <h4 style={{ fontFamily: "var(--font-body)", fontSize: "0.92rem", fontWeight: 500, color: "var(--color-text)", marginBottom: "0.2rem" }}>
            {link.label}
          </h4>
          <p style={{ fontSize: "0.82rem", color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
            {link.desc}
          </p>
        </a>
      ))}
    </div>
  );
}
