"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

/**
 * Post-OAuth bounce. The backend already set the session cookie and redirected
 * here with ?next=. We call /me to hydrate the auth store from that cookie
 * (otherwise ProtectedRoute, which reads the store, would bounce to /signin),
 * then forward to the destination.
 */
export default function CompletePage() {
  const router = useRouter();
  const { setAuthenticated } = useAuthStore();

  useEffect(() => {
    // Only allow internal paths ("/foo") — never "//evil.com" or "https://…".
    const raw = new URLSearchParams(window.location.search).get("next") || "/create";
    const next = raw.startsWith("/") && !raw.startsWith("//") ? raw : "/create";
    authApi
      .me()
      .then((res) => {
        setAuthenticated({
          id: res.data.id,
          email: res.data.email,
          full_name: res.data.full_name,
        });
        router.replace(next);
      })
      .catch(() => router.replace("/signin?error=session"));
  }, [router, setAuthenticated]);

  return (
    <main className="flex min-h-[calc(100vh-60px)] items-center justify-center">
      <p className="text-sm text-[var(--color-muted)]">Signing you in…</p>
    </main>
  );
}
