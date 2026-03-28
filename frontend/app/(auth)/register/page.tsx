"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { formCardStyle, formInputStyle, formLabelStyle, submitBtnStyle } from "@/lib/style";
import { authApi, ApiError } from "@/lib/api";

export default function RegisterPage() {
    const router = useRouter();
    const { setUser } = useAuthStore();

    const [form, setForm] = useState({
        full_name: "",
        email: "",
        password: "",
        confirm: "",
    });
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!form.full_name || !form.email || !form.password || !form.confirm) {
            setError("Please fill in all fields.");
            return;
        }
        if (form.password !== form.confirm) {
            setError("Passwords do not match.");
            return;
        }
        if (form.password.length < 8) {
            setError("Password must be at least 8 characters.");
            return;
        }

        setLoading(true);

        try {
            const res = await authApi.register({
                full_name: form.full_name,
                email: form.email,
                password: form.password,
            });
            setUser({
                id: res.data.id,
                email: res.data.email,
                full_name: res.data.full_name,
            });
            router.push("/settings");
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

    const field = (
        key: keyof typeof form,
        label: string,
        type: string,
        placeholder: string
    ) => (
        <div style={{ marginBottom: "1.1rem" }}>
            <label style={formLabelStyle}>{label}</label>
            <input
                type={type}
                placeholder={placeholder}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                style={formInputStyle}
            />
        </div>
    );

    return (
        <main
            style={{
                minHeight: "calc(100vh - 60px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "2rem 1.5rem",
                backgroundColor: "var(--color-bg)",
            }}
        >
            <div style={{ width: "100%", maxWidth: "400px" }}>
                <div style={{ marginBottom: "2.5rem", textAlign: "center" }}>
                    <h1
                        style={{
                            fontFamily: "var(--font-display)",
                            fontSize: "2rem",
                            fontWeight: 400,
                            letterSpacing: "-0.02em",
                            color: "var(--color-text)",
                            marginBottom: "0.5rem",
                        }}
                    >
                        Create an account
                    </h1>
                    <p
                        style={{
                            fontSize: "0.88rem",
                            color: "var(--color-text-muted)",
                            fontFamily: "var(--font-body)",
                        }}
                    >
                        Join Cupid and start connecting
                    </p>
                </div>

                <div style={formCardStyle}>
                    <form onSubmit={handleSubmit}>
                        {field("full_name", "Full Name", "text", "Your full name")}
                        {field("email", "Email", "email", "you@example.com")}
                        {field("password", "Password", "password", "••••••••")}
                        {field("confirm", "Confirm Password", "password", "••••••••")}

                        {error && (
                            <p
                                style={{
                                    fontSize: "0.82rem",
                                    color: "#c0392b",
                                    marginBottom: "1rem",
                                    fontFamily: "var(--font-body)",
                                }}
                            >
                                {error}
                            </p>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            style={{
                                ...submitBtnStyle,
                                opacity: loading ? 0.7 : 1,
                                cursor: loading ? "not-allowed" : "pointer",
                            }}
                        >
                            {loading ? "Creating account..." : "Create account"}
                        </button>
                    </form>
                </div>

                <p
                    style={{
                        textAlign: "center",
                        marginTop: "1.5rem",
                        fontSize: "0.84rem",
                        color: "var(--color-text-muted)",
                        fontFamily: "var(--font-body)",
                    }}
                >
                    Already have an account?{" "}
                    <Link
                        href="/login"
                        style={{
                            color: "var(--color-primary)",
                            textDecoration: "none",
                            fontWeight: 500,
                        }}
                    >
                        Sign in
                    </Link>
                </p>
            </div>
        </main>
    );
}
