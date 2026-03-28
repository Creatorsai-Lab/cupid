"use client";

import { useState, useEffect } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuthStore } from "@/lib/store";
import { User, Sparkles, HelpCircle, Settings } from "lucide-react";
import { authApi, profileApi } from "@/lib/api";
import { useRouter } from "next/navigation";

const TABS = [
    { id: "personalization", label: "Personalization", icon: User },
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

function PersonalizationTab({ userName, userEmail }: { userName?: string; userEmail?: string }) {
    const [form, setForm] = useState({
        name: userName || "",
        bio: "",
        field: "",
        skills: "",
        geography: "",
        audience: "",
    });
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [loading, setLoading] = useState(true);

    // Load existing profile on mount
    useEffect(() => {
        const loadProfile = async () => {
            try {
                const res = await profileApi.get();
                if (res.data) {
                    setForm((prev) => ({
                        ...prev,
                        bio: res.data?.bio || "",
                        field: res.data?.field || "",
                        skills: res.data?.skills || "",
                        geography: res.data?.geography || "",
                        audience: res.data?.audience || "",
                    }));
                }
            } catch {
                // Profile doesn't exist yet — that's fine
            } finally {
                setLoading(false);
            }
        };
        loadProfile();
    }, []);

    const handleSave = async () => {
        setSaving(true);
        setSaved(false);
        try {
            await profileApi.update({
                bio: form.bio || undefined,
                field: form.field || undefined,
                skills: form.skills || undefined,
                geography: form.geography || undefined,
                audience: form.audience || undefined,
            });
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (err) {
            console.error("Failed to save profile:", err);
        } finally {
            setSaving(false);
        }
    };

    const cardStyle: React.CSSProperties = {
        backgroundColor: "white",
        border: "1px solid var(--color-border)",
        borderRadius: "12px",
        padding: "1.5rem",
        marginBottom: "1.5rem",
    };

    const labelStyle: React.CSSProperties = {
        display: "block",
        fontSize: "0.82rem",
        fontWeight: 500,
        color: "var(--color-text)",
        marginBottom: "0.35rem",
        fontFamily: "var(--font-body)",
    };

    const inputStyle: React.CSSProperties = {
        display: "block",
        width: "100%",
        height: "40px",
        padding: "0 0.8rem",
        borderRadius: "8px",
        border: "1px solid var(--color-border)",
        backgroundColor: "var(--color-background)",
        color: "var(--color-text)",
        fontSize: "0.88rem",
        fontFamily: "var(--font-body)",
        outline: "none",
    };

    const textareaStyle: React.CSSProperties = {
        ...inputStyle,
        height: "80px",
        padding: "0.6rem 0.8rem",
        resize: "vertical" as const,
    };

    if (loading) {
        return <p style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)", fontSize: "0.85rem" }}>Loading profile...</p>;
    }

    return (
        <div>
            <div style={cardStyle}>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", fontWeight: 400, marginBottom: "1rem", color: "var(--color-text)" }}>
                    Profile
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                    <div>
                        <label style={labelStyle}>Full Name</label>
                        <input style={inputStyle} value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    </div>
                    <div>
                        <label style={labelStyle}>Email</label>
                        <input style={{ ...inputStyle, opacity: 0.6 }} value={userEmail || ""} disabled />
                    </div>
                </div>
            </div>

            <div style={cardStyle}>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", fontWeight: 400, marginBottom: "0.25rem", color: "var(--color-text)" }}>
                    Persona Setup
                </h3>
                <p style={{ fontSize: "0.82rem", color: "var(--color-muted)", fontFamily: "var(--font-body)", marginBottom: "1rem" }}>
                    This information is used by your Persona Agent to learn your voice.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div>
                        <label style={labelStyle}>Bio / About You</label>
                        <textarea style={textareaStyle} placeholder="e.g., AI engineer building open-source tools"
                            value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                        <div>
                            <label style={labelStyle}>Field / Domain</label>
                            <input style={inputStyle} placeholder="e.g., AI/ML Engineering"
                                value={form.field} onChange={(e) => setForm({ ...form, field: e.target.value })} />
                        </div>
                        <div>
                            <label style={labelStyle}>Geography</label>
                            <input style={inputStyle} placeholder="e.g., India"
                                value={form.geography} onChange={(e) => setForm({ ...form, geography: e.target.value })} />
                        </div>
                    </div>
                    <div>
                        <label style={labelStyle}>Skills & Interests</label>
                        <input style={inputStyle} placeholder="e.g., Python, LangGraph, systems design"
                            value={form.skills} onChange={(e) => setForm({ ...form, skills: e.target.value })} />
                    </div>
                    <div>
                        <label style={labelStyle}>Target Audience</label>
                        <input style={inputStyle} placeholder="e.g., Technical professionals, indie hackers"
                            value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })} />
                    </div>
                </div>

                <button className="btn-primary" style={{ marginTop: "1.5rem" }} onClick={handleSave} disabled={saving}>
                    {saving ? "Saving..." : saved ? "✓ Saved" : "Save"}
                </button>
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
