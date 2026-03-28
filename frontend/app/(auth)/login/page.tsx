"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { authApi, ApiError } from "@/lib/api";
import { formCardStyle, formInputStyle, formLabelStyle, submitBtnStyle } from "@/lib/style";

export default function LoginPage() {
    const router = useRouter();
    const { setUser } = useAuthStore();

    const [form, setForm] = useState({ email: "", password: "" });
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!form.email || !form.password) {
            setError("Please fill in all fields.");
            return;
        }

        setLoading(true);

        try {
            const res = await authApi.login({
                email: form.email,
                password: form.password,
            });
            setUser({
                id: res.data.id,
                email: res.data.email,
                full_name: res.data.full_name,
            });
            router.push("/create");      // Login → create page
        } catch (err: unknown) {
            if (err instanceof ApiError) {
                setError(err.message);
            } else {
                setError("Something went wrong. Is the backend running?");
            }
        } finally {
            setLoading(false);
        }
    };

    // ... rest of the JSX stays the same
    return (
        <main
            style={{
                minHeight: "calc(100vh - 60px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "2rem 1.5rem",
            }}
        >
            <div style={{ width: "100%", maxWidth: "400px" }}>
                <div style={{ marginBottom: "2.5rem", textAlign: "center" }}>
                    <h1>Welcome back to Cupid's login.</h1>
                    <p style={{ fontSize: "0.88rem", color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                        Enter your details correctly to pick up your content creation journey!
                    </p>
                </div>

                <div style={formCardStyle}>
                    <form onSubmit={handleSubmit}>
                        <div style={{ marginBottom: "1.1rem" }}>
                            <label style={formLabelStyle}>Email</label>
                            <input type="email" autoComplete="email" placeholder="you@example.com"
                                value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                                style={formInputStyle} />
                        </div>
                        <div style={{ marginBottom: "1.5rem" }}>
                            <label style={formLabelStyle}>Password</label>
                            <input type="password" autoComplete="current-password" placeholder="••••••••"
                                value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                                style={formInputStyle} />
                        </div>

                        {error && (
                            <p style={{ fontSize: "0.82rem", color: "#c0392b", marginBottom: "1rem", fontFamily: "var(--font-body)" }}>
                                {error}
                            </p>
                        )}

                        <button type="submit" disabled={loading}
                            style={{ ...submitBtnStyle, opacity: loading ? 0.7 : 1, cursor: loading ? "not-allowed" : "pointer" }}>
                            {loading ? "Signing in..." : "Sign in"}
                        </button>
                    </form>
                </div>

                <p style={{ textAlign: "center", marginTop: "1.5rem", fontSize: "0.84rem", color: "var(--color-muted)", fontFamily: "var(--font-body)" }}>
                    No account yet?{" "}
                    <Link href="/register" style={{ color: "var(--color-primary)", fontWeight: 500 }}>
                        Create one
                    </Link>
                </p>
            </div>
        </main>
    );
}
