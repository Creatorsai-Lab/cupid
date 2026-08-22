"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const ERRORS: Record<string, string> = {
  oauth: "Sign-in was cancelled or failed. Please try again.",
  unverified: "Your Google email isn't verified — use a verified Google account.",
  session: "Could not start your session. Please try again.",
};

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8a12 12 0 1 1 0-24c3 0 5.8 1.1 7.9 3l5.7-5.7A20 20 0 1 0 24 44a20 20 0 0 0 19.6-23.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8A12 12 0 0 1 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7A20 20 0 0 0 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2A12 12 0 0 1 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3a12 12 0 0 1-4.1 5.6l6.2 5.2C39.9 36.5 44 31 44 24c0-1.2-.1-2.4-.4-3.5z" />
    </svg>
  );
}

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("error");
    if (code) setError(ERRORS[code] ?? "Something went wrong. Please try again.");
  }, []);

  const signIn = () => {
    window.location.href = `${API}/api/v1/auth/google/login`;
  };

  return (
    <main className="flex min-h-[calc(100vh-60px)] items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-2xl border border-[var(--color-border)] bg-white p-8 text-center shadow-sm">
        <h1 className="text-2xl tracking-tight">Welcome to Cupid</h1>
        <p className="mt-2 text-sm text-[var(--color-muted)]">
          Sign in to start creating content that sounds like you.
        </p>

        {error && (
          <p className="mt-4 rounded-lg bg-[color-mix(in_srgb,var(--color-destructive)_12%,transparent)] px-3 py-2 text-sm text-[var(--color-destructive)]">
            {error}
          </p>
        )}

        <button
          onClick={signIn}
          className="mt-6 flex w-full items-center justify-center gap-3 rounded-lg border border-[var(--color-border)] bg-white px-4 py-3 text-sm font-medium text-[var(--color-text)] transition-colors hover:bg-[#fff6ed]"
        >
          <GoogleIcon />
          Continue with Google
        </button>

        <p className="mt-6 text-xs text-[var(--color-muted)]">
          By continuing you agree to our{" "}
          <a href="/terms" className="underline">
            Terms
          </a>{" "}
          and{" "}
          <a href="/privacy" className="underline">
            Privacy Policy
          </a>
          .
        </p>
      </div>
    </main>
  );
}
